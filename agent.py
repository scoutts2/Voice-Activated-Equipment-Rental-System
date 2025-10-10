"""
Main LiveKit Voice Agent for Equipment Rental System.
Handles the 7-stage rental workflow through voice conversations.
"""

import asyncio
import logging
from typing import Dict, Optional
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession
import livekit.plugins.openai
import livekit.plugins.deepgram
import livekit.plugins.elevenlabs


from config import config
from services.verification_service import (
    verify_business_license,
    verify_operator_credentials,
    verify_site_safety,
    verify_insurance_coverage
)
from services.sheets_service import (
    get_available_equipment,
    get_equipment_by_id,
    update_equipment_status
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: Each session will have its own state instance
# We store it as a session-specific variable, not global


class ConversationState:
    """
    Tracks the current state of the rental conversation.
    Remembers which stage we're on and customer data collected so far.
    """
    def __init__(self):
        # Current stage (1-7)
        self.stage = 1
        
        # Customer information collected during conversation
        self.customer_license = None
        self.selected_equipment_id = None
        self.selected_equipment = None
        self.agreed_price = None
        self.operator_license = None
        self.operator_name = None
        self.job_address = None
        self.insurance_policy = None
        
        # Flags
        self.verification_passed = False
        self.booking_completed = False
        
        # Negotiation tracking
        self.current_price_offer = None  # Track the current price being negotiated
        self.negotiation_count = 0  # Track how many times customer has negotiated


# Function tools that GPT-4 can call during conversation
@function_tool
async def verify_business_license_tool(license_number: str):
    """Verify customer's business license with state authorities."""
    logger.info(f"Verifying business license: {license_number}")
    
    is_valid = verify_business_license(license_number)
    
    if is_valid:
        return f"Business license {license_number} verified successfully. You can proceed to equipment selection."
    else:
        return f"Business license {license_number} could not be verified. Please check the number or contact support."


@function_tool
async def get_equipment_details_tool(equipment_id: str):
    """Get detailed information about specific equipment. NEVER reveal max rate or minimum rate to customer."""
    logger.info(f"Getting equipment details for: {equipment_id}")
    
    equipment = get_equipment_by_id(equipment_id)
    
    if not equipment:
        return f"Equipment {equipment_id} not found."
    
    # Return details WITHOUT revealing max rate or minimum rate (those are for internal use only)
    return f"""Equipment Details:
- Name: {equipment['Equipment Name']}
- Category: {equipment['Category']}
- Daily Rate: ${equipment['Daily Rate']}
- Operator Cert Required: {equipment['Operator Cert Required']}
- Min Insurance: ${equipment['Min Insurance']:,}
- Storage Location: {equipment['Storage Location']}
- Weight Class: {equipment['Weight Class']}"""


@function_tool
async def negotiate_price_tool(equipment_id: str, customer_response: str, urgency_level: str = "normal"):
    """
    Handle pricing negotiation based on customer response and urgency.
    Progressively lowers price from daily rate toward minimum rate.
    urgency_level: "low", "normal", "high", "critical"
    """
    logger.info(f"Negotiating price for {equipment_id}, urgency: {urgency_level}, negotiation count: {state.negotiation_count}")
    
    equipment = get_equipment_by_id(equipment_id)
    if not equipment:
        return "Equipment not found for negotiation."
    
    daily_rate = int(equipment['Daily Rate'])
    min_rate = int(equipment.get('Minimum Rate', daily_rate * 0.8))
    
    # If this is the first negotiation, start with the daily rate
    if state.current_price_offer is None:
        state.current_price_offer = daily_rate
    
    # Check if customer is accepting the current offer
    if any(word in customer_response.lower() for word in ["yes", "accept", "good", "ok", "fine", "deal", "sounds good"]):
        state.agreed_price = state.current_price_offer
        logger.info(f"Customer accepted price: ${state.current_price_offer}")
        return f"Excellent! ${state.current_price_offer} per day it is. Let's move forward with the next step."
    
    # Customer wants a lower price - negotiate down
    if any(phrase in customer_response.lower() for phrase in ["too expensive", "too much", "lower", "struggling", "cheaper", "better price", "discount", "negotiate"]):
        state.negotiation_count += 1
        current_offer = state.current_price_offer
        
        # Calculate how much room we have to negotiate
        negotiation_range = current_offer - min_rate
        
        # If we're already at or below minimum, hold firm (but NEVER reveal the actual minimum)
        if current_offer <= min_rate:
            logger.info(f"At minimum price: ${min_rate}")
            return f"I understand your budget concerns. Unfortunately, ${current_offer} is the absolute lowest rate I can offer for this equipment. This is already a special rate and I really can't go any lower. Can you work with this price?"
        
        # Determine discount amount based on urgency and negotiation count
        # Start generous, get smaller with each negotiation
        if urgency_level == "critical":
            discount_percent = 0.35 - (state.negotiation_count * 0.05)  # 35%, 30%, 25%, 20%...
        elif urgency_level == "high":
            discount_percent = 0.30 - (state.negotiation_count * 0.05)  # 30%, 25%, 20%, 15%...
        elif urgency_level == "low":
            discount_percent = 0.15 - (state.negotiation_count * 0.03)  # 15%, 12%, 9%, 6%...
        else:  # normal
            discount_percent = 0.25 - (state.negotiation_count * 0.05)  # 25%, 20%, 15%, 10%...
        
        # Make sure we don't give negative discounts
        discount_percent = max(0.02, discount_percent)  # Minimum 2% discount per negotiation
        
        # Calculate new offer
        discount_amount = int(negotiation_range * discount_percent)
        new_offer = max(min_rate, current_offer - discount_amount)
        
        # Update state
        state.current_price_offer = new_offer
        
        logger.info(f"Lowering price from ${current_offer} to ${new_offer} (discount: ${discount_amount})")
        
        # Response varies based on how close we are to minimum
        remaining_room = new_offer - min_rate
        if remaining_room < 50:
            return f"I really want to make this work for you. I can go down to ${new_offer} per day, but that's as low as I can go. This is already below our standard rate. What do you think?"
        elif remaining_room < 200:
            return f"I understand your situation. I can offer ${new_offer} per day. This is a very competitive rate for this equipment. Can we move forward with this?"
        else:
            return f"I hear you. Let me see what I can do... I can offer you ${new_offer} per day. This is a special rate I'm able to provide. How does that sound?"
    
    # Default response - customer hasn't clearly accepted or rejected
    return f"The current rate we're discussing is ${state.current_price_offer} per day. Is this within your budget, or would you like to see if we can adjust it further?"


@function_tool
async def book_equipment_tool(equipment_id: str):
    """Book equipment by updating status to RENTED."""
    logger.info(f"Attempting to book equipment: {equipment_id}")
    
    success = update_equipment_status(equipment_id, "RENTED")
    
    if success:
        equipment = get_equipment_by_id(equipment_id)
        return f"""Booking confirmed! 
Equipment: {equipment['Equipment Name']}
Pickup Location: {equipment['Storage Location']}
Status: RENTED

Please note pickup details and rental terms."""
    else:
        return f"Sorry, equipment {equipment_id} is no longer available. It may have been booked by another customer."


@function_tool
async def get_current_stage_tool() -> str:
    """Get the current stage of the rental process."""
    return f"""Current Stage: {state.stage}/7

Stage 1: Customer Verification - Get business license
Stage 2: Equipment Discovery - Find right equipment  
Stage 3: Site Safety Verification - Verify ONLY job site safety
Stage 4: Pricing Negotiation - Negotiate price within range
Stage 5: Operator Certification - Verify operator credentials
Stage 6: Insurance Verification - Verify insurance coverage
Stage 7: Booking Completion - Finalize rental

You are currently in Stage {state.stage}."""


@function_tool
async def move_to_next_stage_tool() -> str:
    """Move to the next stage of the rental process."""
    if state.stage < 7:
        state.stage += 1
        logger.info(f"Moving to stage {state.stage}")
        return f"Moved to Stage {state.stage}. Continue with the next step in the rental process."
    else:
        return "Already at the final stage (7). Complete the booking process."


@function_tool
async def verify_operator_credentials_tool(operator_license: str, certification_type: str) -> str:
    """Verify operator's credentials and license."""
    logger.info(f"Verifying operator credentials: {operator_license} for {certification_type}")
    

    is_valid = verify_operator_credentials(operator_license, certification_type)
    
    if is_valid:
        return f"Operator credentials verified successfully for license {operator_license} in {certification_type}."
    else:
        return f"Operator credentials could not be verified for license {operator_license} in {certification_type}. Please check the license or contact support."


@function_tool
async def verify_site_safety_tool(job_address: str, equipment_category: str, weight_class: str) -> str:
    """Verify job site can safely handle the equipment."""
    logger.info(f"Verifying site safety at {job_address} for {equipment_category} ({weight_class})")
    

    is_valid = verify_site_safety(job_address, equipment_category, weight_class)
    
    if is_valid:
        return f"Site safety verified for {job_address}. The location can safely handle {equipment_category} equipment ({weight_class})."
    else:
        return f"Site safety could not be verified for {job_address}. Please ensure the location can safely handle {equipment_category} equipment ({weight_class}) or contact support."


@function_tool
async def verify_insurance_coverage_tool(policy_number: str, required_amount: int, equipment_value: int) -> str:
    """Verify customer's insurance coverage meets requirements."""
    logger.info(f"Verifying insurance coverage: {policy_number}, required: ${required_amount:,}, equipment value: ${equipment_value:,}")
    
    is_valid = verify_insurance_coverage(policy_number, required_amount, equipment_value)
    
    if is_valid:
        return f"Insurance policy {policy_number} verified successfully. Coverage meets minimum requirements of ${required_amount:,}."
    else:
        return f"Insurance policy {policy_number} could not be verified or does not meet minimum requirements of ${required_amount:,}. Please update your coverage."


@function_tool
async def get_stage_instructions_tool() -> str:
    """Get detailed instructions for the current stage."""
    stage_instructions = {
        1: """Stage 1 - Customer Verification:
- Ask for their business license number
- When they provide it, call verify_business_license_tool(license_number)
- IF tool returns "verified successfully", call move_to_next_stage_tool()
- IF verification fails, ask them to check the number or contact support""",
        
        2: """Stage 2 - Equipment Discovery:
- Ask what type of project they're working on and what they need
- Show available equipment that matches their needs
- When they ask about specific equipment, call get_equipment_details_tool(equipment_id)
- Help them narrow down to 1-2 options
- When they've selected equipment, call move_to_next_stage_tool()""",
        
        3: """Stage 3 - Site Safety Verification (SITE SAFETY ONLY - NOT OPERATOR OR INSURANCE):
- Confirm the selected equipment
- Ask for the job site address
- When they provide it, call verify_site_safety_tool(job_address, equipment_category, weight_class)
- Use the Category and Weight Class fields from the selected equipment
- IMMEDIATELY call move_to_next_stage_tool() after site safety is verified
- DO NOT ask about operator credentials - that comes in Stage 5
- DO NOT ask about insurance - that comes in Stage 6
- DO NOT discuss pricing - that comes in Stage 4""",
        
        4: """Stage 4 - Pricing Negotiation:
- Show ONLY the daily rate for selected equipment (DO NOT mention max rate)
- Use negotiate_price_tool(equipment_id, customer_response, urgency_level) to handle negotiations
- Determine urgency_level based on customer language: "urgent/critical/emergency" = "critical", "asap/soon" = "high", casual = "normal", "no rush" = "low"
- Start with daily rate, negotiate down gradually based on customer objections
- Only go to minimum rate in worst case scenarios
- Confirm final price
- When price is agreed, call move_to_next_stage_tool()""",
        
        5: """Stage 5 - Operator Certification:
- Ask for operator's license number
- Use the Operator Cert Required field from the selected equipment as certification_type
- When they provide it, call verify_operator_credentials_tool(operator_license, certification_type)
- IF tool returns "verified successfully", call move_to_next_stage_tool()
- IF verification fails, ask them to provide correct credentials""",
        
        6: """Stage 6 - Insurance Verification:
- Ask for their insurance policy number
- When they provide it, call verify_insurance_coverage_tool(policy_number, required_amount, equipment_value)
- Use the Min Insurance amount from the selected equipment as required_amount
- Use the Daily Rate * 30 as equipment_value (approximate replacement value)
- IF tool returns "verified successfully", call move_to_next_stage_tool()
- IF verification fails, ask them to update coverage""",
        
        7: """Stage 7 - Booking Completion:
- FIRST: Call book_equipment_tool(equipment_id) to finalize the rental
- THEN: Confirm all details (equipment, price, dates, operator, insurance, pickup location)
- FINALLY: Call end_conversation_tool() after customer acknowledges completion
- Thank the customer for their business"""
    }
    
    return stage_instructions.get(state.stage, "Unknown stage")


@function_tool
async def end_conversation_tool() -> str:
    """
    Mark the conversation as complete and provide final message.
    Call this when: booking is complete, customer says goodbye/done/all set, or customer cancels.
    """
    logger.info("Marking conversation as complete")
    state.booking_completed = True
    return """Rental process complete! Thank you for choosing Metro Equipment Rentals. 
You can now press Q to exit, or ask any follow-up questions if needed."""


async def entrypoint(ctx: JobContext):
    """
    Main entry point - called when a customer connects (phone call or web).
    Sets up the voice assistant and starts the conversation.
    """
    global state
    logger.info("Starting new rental conversation")
    
    # Create conversation state to track progress
    state = ConversationState()
    
    # Connect to room 
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    logger.info("Connected to room, ready to assist customer")
    
    # Build initial system prompt with equipment data
    available_equipment = get_available_equipment()
    
    initial_prompt = f"""You are a professional equipment rental agent for {config.COMPANY_NAME}.

Your job is to help customers rent construction equipment through a 7-stage process:

1. Customer Verification - Get and verify their business license
2. Equipment Discovery - Help them find the right equipment
3. Site Safety Verification - Verify ONLY job site safety
4. Pricing Negotiation - Negotiate price within allowed range
5. Operator Certification - Verify operator credentials
6. Insurance Verification - Verify insurance coverage
7. Booking Completion - Finalize the rental

CURRENT STAGE: Stage 1 - Customer Verification

AVAILABLE EQUIPMENT:
{available_equipment}

       IMPORTANT: You have access to these tools to help customers:
       - get_current_stage_tool() - Check which stage you're in
       - get_stage_instructions_tool() - Get detailed instructions for current stage
       - move_to_next_stage_tool() - Move to the next stage when ready
       - verify_business_license_tool(license_number) - Verify customer's business license
       - get_equipment_details_tool(equipment_id) - Get details about specific equipment
       - negotiate_price_tool(equipment_id, customer_response, urgency_level) - Handle pricing negotiations
       - verify_site_safety_tool(job_address, equipment_category, weight_class) - Verify job site safety
       - verify_operator_credentials_tool(operator_license, certification_type) - Verify operator credentials
       - verify_insurance_coverage_tool(policy_number, required_amount, equipment_value) - Verify insurance
       - book_equipment_tool(equipment_id) - Book equipment and finalize rental
       - end_conversation_tool() - End the conversation when rental is complete or customer is done

WORKFLOW INSTRUCTIONS:
- You MUST complete stages ONE AT A TIME in order (1→2→3→4→5→6→7)
- NEVER skip ahead or ask for information from future stages
- After EVERY customer response, call get_current_stage_tool() to check which stage you're in
- Call get_stage_instructions_tool() to see what to do in the current stage
- Follow the stage instructions EXACTLY - only do what that stage says
- Call move_to_next_stage_tool() ONLY when the current stage is complete
- NEVER ask for operator credentials, insurance, or pricing until you reach those specific stages
- Be friendly and professional throughout the conversation
- Confirm details by repeating them back to the customer

       CRITICAL TOOL CALLING RULES:
       - You MUST actually call the tools using function calls, not just describe calling them
       - DO NOT say "Calling tool..." and then make up a response
       - WAIT for the actual tool response before telling the customer the result
       - The tool will return the actual result - use that exact result in your response
       - Example: Call verify_business_license_tool(123), WAIT for response, then tell customer the result

       PRICING NEGOTIATION STRATEGY:
       - In Stage 4, start by stating ONLY the daily rate (NEVER mention max rate or minimum rate)
       - Use negotiate_price_tool() to handle all pricing discussions
       - Determine urgency_level from customer language: "urgent/critical/emergency" = "critical", "asap/soon" = "high", casual = "normal", "no rush" = "low"
       - If customer says price is "too expensive" or "too much", use negotiate_price_tool() to offer a lower price
       - Negotiate gradually - start with daily rate, then work down based on customer objections
       - CRITICAL: NEVER reveal the minimum rate to the customer, even when pressed
       - Only offer minimum rate in worst-case scenarios when customer is very price-sensitive
       - Try to maximize profit while keeping the customer satisfied

ENDING THE CONVERSATION:
- After completing Stage 7 (booking), call end_conversation_tool() to close the session
- If customer says "goodbye", "I'm done", "that's all", or similar, call end_conversation_tool()
- If customer decides not to rent (cancels), call end_conversation_tool()

CRITICAL GREETING REQUIREMENT: You MUST start EVERY conversation by greeting the customer first. When you receive ANY message from the customer (even just "hello" or "hi"), respond with: "Hello! Welcome to Metro Equipment Rentals. How can I assist you with your equipment rental needs today?" Then proceed with the 7-stage workflow. Always be proactive and welcoming.
"""
    
    logger.info(f"Loaded {len(available_equipment)} available equipment items")
    
    # Collect all the function tools
    tools = [
        verify_business_license_tool,
        get_equipment_details_tool,
        negotiate_price_tool,
        book_equipment_tool,
        get_current_stage_tool,
        move_to_next_stage_tool,
        verify_operator_credentials_tool,
        verify_site_safety_tool,
        verify_insurance_coverage_tool,
        get_stage_instructions_tool,
        end_conversation_tool,
    ]
    
    # Create the voice agent with AI models and tools
    agent = Agent(
        instructions=initial_prompt,
        tools=tools,  
    )
    
    logger.info(f"Voice agent created and configured with {len(tools)} tools")
    
    # Create OpenAI LLM instance
    # The @function_tool decorator should register tools globally and make them available to ANY LLM instance created

    openai_llm = livekit.plugins.openai.LLM(model="gpt-4o")
    
    logger.info("Created OpenAI LLM instance with gpt-4o model")
    
    # Create AgentSession with STT, LLM, TTS
    # VOICE MODE ENABLED for phone calls and production use
    logger.info("Initializing voice-enabled agent session...")
    logger.info(f"STT: deepgram/nova-2")
    logger.info(f"TTS: openai/tts-1")
    
    session = AgentSession(
        stt="deepgram/nova-2",  # Deepgram Speech-to-Text
        llm=openai_llm,  # OpenAI GPT-4o
        tts="openai/tts-1",  # OpenAI Text-to-Speech (testing)
    )
    
    logger.info("Voice-enabled agent session created successfully")
    
    # For TEXT-ONLY console testing, use this instead:
    # session = AgentSession(
    #     stt=None,
    #     llm=openai_llm,
    #     tts=None,
    # )
    
    # Start the session with the agent and room
    logger.info("Starting agent session...")
    await session.start(
        room=ctx.room,
        agent=agent,
    )
    
    logger.info("Voice agent started and ready for calls")
    logger.info("Agent is now live and can handle phone calls via LiveKit Telephony")
    logger.info(f"Room name: {ctx.room.name}")
    logger.info(f"Agent name: equipment-rental-agent")
    
    # Note: In console mode, the agent will greet the user when they first type a message
    # The system prompt is configured to greet immediately when conversation starts
    
    # Session stays open until user presses Q to quit
    # The end_conversation_tool will mark the rental as complete but won't force-close the session, and allows follow-up questions



if __name__ == "__main__":
    """Run the agent when this file is executed."""
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="equipment-rental-agent"  # Required for playground connection
    ))

