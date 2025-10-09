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

# Import our services
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


# Function tools that GPT-4 can call during conversation
# These MUST be defined before the entrypoint function
@function_tool
async def verify_business_license_tool(license_number: str):
    """Verify customer's business license with state authorities."""
    logger.info(f"Verifying business license: {license_number}")
    
    # Call our verification service
    is_valid = verify_business_license(license_number)
    
    if is_valid:
        return f"Business license {license_number} verified successfully. You can proceed to equipment selection."
    else:
        return f"Business license {license_number} could not be verified. Please check the number or contact support."


@function_tool
async def get_equipment_details_tool(equipment_id: str):
    """Get detailed information about specific equipment."""
    logger.info(f"Getting equipment details for: {equipment_id}")
    
    equipment = get_equipment_by_id(equipment_id)
    
    if not equipment:
        return f"Equipment {equipment_id} not found."
    
    return f"""Equipment Details:
- Name: {equipment['Equipment Name']}
- Category: {equipment['Category']}
- Daily Rate: ${equipment['Daily Rate']}
- Max Rate: ${equipment['Max Rate']}
- Operator Cert Required: {equipment['Operator Cert Required']}
- Min Insurance: ${equipment['Min Insurance']:,}
- Storage Location: {equipment['Storage Location']}
- Weight Class: {equipment['Weight Class']}"""


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
    
    # Call our verification service
    is_valid = verify_operator_credentials(operator_license, certification_type)
    
    if is_valid:
        return f"Operator credentials verified successfully for license {operator_license} in {certification_type}."
    else:
        return f"Operator credentials could not be verified for license {operator_license} in {certification_type}. Please check the license or contact support."


@function_tool
async def verify_site_safety_tool(job_address: str, equipment_category: str, weight_class: str) -> str:
    """Verify job site can safely handle the equipment."""
    logger.info(f"Verifying site safety at {job_address} for {equipment_category} ({weight_class})")
    
    # Call our verification service
    is_valid = verify_site_safety(job_address, equipment_category, weight_class)
    
    if is_valid:
        return f"Site safety verified for {job_address}. The location can safely handle {equipment_category} equipment ({weight_class})."
    else:
        return f"Site safety could not be verified for {job_address}. Please ensure the location can safely handle {equipment_category} equipment ({weight_class}) or contact support."


@function_tool
async def verify_insurance_coverage_tool(policy_number: str, required_amount: int, equipment_value: int) -> str:
    """Verify customer's insurance coverage meets requirements."""
    logger.info(f"Verifying insurance coverage: {policy_number}, required: ${required_amount:,}, equipment value: ${equipment_value:,}")
    
    # Call our verification service
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
- Show the daily rate for selected equipment
- Ask if they need multiple days
- Negotiate price within the allowed range (daily rate to max rate)
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
    
    # Connect to the room (the call/conversation space)
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

ENDING THE CONVERSATION:
- After completing Stage 7 (booking), call end_conversation_tool() to close the session
- If customer says "goodbye", "I'm done", "that's all", or similar, call end_conversation_tool()
- If customer decides not to rent (cancels), call end_conversation_tool()

IMPORTANT: When the conversation starts, IMMEDIATELY greet the customer warmly and ask how you can help with their equipment rental needs. Do NOT wait for the customer to speak first.
"""
    
    logger.info(f"Loaded {len(available_equipment)} available equipment items")
    
    # Collect all the function tools
    tools = [
        verify_business_license_tool,
        get_equipment_details_tool,
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
        tools=tools,  # Pass the tools to the agent
    )
    
    logger.info(f"Voice agent created and configured with {len(tools)} tools")
    
    # Create OpenAI LLM instance
    # The @function_tool decorator should register tools globally
    # and make them available to ANY LLM instance created
    openai_llm = livekit.plugins.openai.LLM(model="gpt-4o")
    
    logger.info("Created OpenAI LLM instance with gpt-4o model")
    
    # Create AgentSession with STT, LLM, TTS
    # For TEXT mode: Keep STT/TTS as None to save LiveKit connection slots
    # For VOICE mode: Uncomment the lines below to enable speech
    session = AgentSession(
        stt=None,  # For voice mode: use "deepgram/nova-2"
        llm=openai_llm,  # LLM instance should have access to globally registered tools
        tts=None,  # For voice mode: use "elevenlabs/multilingual-v2"
    )
    
    # To enable voice mode, replace the session above with:
    # session = AgentSession(
    #     stt="deepgram/nova-2",
    #     llm=openai_llm,
    #     tts="elevenlabs/multilingual-v2",
    # )
    
    # Start the session with the agent and room
    await session.start(
        room=ctx.room,
        agent=agent,
    )
    
    logger.info("Voice agent started, ready to converse in text mode")
    logger.info("Press Ctrl+B to switch to text mode, then type your messages")
    
    # Session stays open until user presses Q to quit
    # The end_conversation_tool will mark the rental as complete
    # but won't force-close the session (allows follow-up questions)


if __name__ == "__main__":
    """Run the agent when this file is executed."""
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

