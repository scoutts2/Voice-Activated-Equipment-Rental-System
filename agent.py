"""
Main LiveKit Voice Agent for Equipment Rental System.
Handles the 7-stage rental workflow through voice conversations.
"""

import asyncio
import logging
import sys
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


logger = logging.getLogger("equipment-rental-agent")
logger.setLevel(logging.INFO)

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
async def negotiate_price_tool(equipment_id: str, action: str):
    """
    Negotiate equipment pricing.
    
    Args:
        equipment_id: The equipment ID
        action: Either "offer_discount" to lower the price, or "accept_price" when customer agrees
    
    Returns pricing information and next steps.
    """
    logger.info(f"negotiate_price_tool called: equipment={equipment_id}, action={action}, negotiation_count={state.negotiation_count}")
    
    equipment = get_equipment_by_id(equipment_id)
    if not equipment:
        return "Equipment not found."
    
    daily_rate = int(equipment['Daily Rate'])
    min_rate = int(equipment.get('Minimum Rate', daily_rate * 0.8))
    
    # Initialize price offer if first time
    if state.current_price_offer is None:
        state.current_price_offer = daily_rate
    
    if action == "accept_price":
        # Customer accepted the current price
        state.agreed_price = state.current_price_offer
        logger.info(f"Customer accepted price: ${state.current_price_offer}")
        return f"Price agreed: ${state.current_price_offer} per day. Pricing is complete. Now call move_to_next_stage_tool() to proceed to operator certification."
    
    elif action == "offer_discount":
        # Offer a discounted price
        state.negotiation_count += 1
        current_offer = state.current_price_offer
        
        # If already at minimum, hold firm
        if current_offer <= min_rate:
            logger.info(f"Already at minimum price: ${min_rate}")
            return f"Current offer: ${current_offer} per day. This is already our absolute lowest rate. We cannot go lower. If customer accepts, call negotiate_price_tool(equipment_id, 'accept_price')."
        
        # Calculate discount(decreases with each negotiation)
        negotiation_range = current_offer - min_rate
        discount_percent = max(0.10, 0.25 - (state.negotiation_count * 0.05))  # 25%, 20%, 15%, 10%...
        discount_amount = int(negotiation_range * discount_percent)
        new_offer = max(min_rate, current_offer - discount_amount)
        
        # Update state
        state.current_price_offer = new_offer
        logger.info(f"Lowered price from ${current_offer} to ${new_offer}")
        
        # Return the new offer with guidance
        remaining_room = new_offer - min_rate
        if remaining_room < 50:
            return f"New offer: ${new_offer} per day. This is as low as we can go (at minimum rate). Tell customer this is the best rate possible. If they accept, call negotiate_price_tool(equipment_id, 'accept_price')."
        else:
            return f"New offer: ${new_offer} per day. You can still negotiate lower if needed. Current offer is ${new_offer - min_rate} above minimum. If customer accepts, call negotiate_price_tool(equipment_id, 'accept_price')."
    
    else:
        return f"Invalid action. Use 'offer_discount' to lower price or 'accept_price' when customer agrees. Current price: ${state.current_price_offer}"


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
    

    is_valid= verify_operator_credentials(operator_license, certification_type)
    
    if is_valid:
        return f"Operator credentials verified successfully for license {operator_license} in {certification_type}."
    else:
        return f"Operator credentials could not be verified for license {operator_license} in {certification_type}. Please check the license or contact support."


@function_tool
async def verify_site_safety_tool(job_address: str, equipment_category: str, weight_class: str) -> str:
    """Verify job site can safely handle the equipment."""
    logger.info(f"Verifying site safety at {job_address} for {equipment_category} ({weight_class})")
    

    is_valid =verify_site_safety(job_address, equipment_category, weight_class)
    
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
- Start by quoting ONLY the daily rate: "The daily rate is $[amount] per day"
- DO NOT mention minimum rate or max rate to the customer
- Listen to customer response:
  * IF customer says price is too high / wants discount / makes counter-offer:
    - Call negotiate_price_tool(equipment_id, "offer_discount") to get a lower price
    - Present the new price to the customer naturally
    - Repeat until customer accepts or you reach minimum
  * IF customer accepts the price (says yes/ok/that works/sounds good):
    - Call negotiate_price_tool(equipment_id, "accept_price") to lock in the price
    - Tool will automatically tell you to call move_to_next_stage_tool()
- Be persuasive but fair - try to close at a good price without immediately dropping to minimum""",
        
        5: """Stage 5 - Operator Certification:
- FIRST, inform the customer what credentials are required: "To operate this equipment, you'll need [certification_type from equipment's Operator Cert Required field]"
- THEN, ask ONLY for their certification number: "What is your certification number?"
- When they provide the certification number, call verify_operator_credentials_tool(operator_license, certification_type)
- IF tool returns "verified successfully", call move_to_next_stage_tool()
- IF verification fails, ask them to provide correct credentials""",
        
        6: """Stage 6 - Insurance Verification:
- FIRST, inform the customer of insurance requirements: "For this rental, you'll need insurance coverage of at least $[Min Insurance amount from equipment] to cover the equipment value"
- THEN, ask ONLY for their policy number: "What is your insurance policy number?"
- When they provide the policy number, call verify_insurance_coverage_tool(policy_number, required_amount, equipment_value)
- Use the EXACT "Min Insurance" value from the selected equipment's Google Sheets data for BOTH required_amount AND equipment_value
- DO NOT calculate or make up insurance values - use the exact value from the equipment data
- IF tool returns "verified successfully", call move_to_next_stage_tool()
- IF verification fails, ask them to update coverage""",
        
        7: """Stage 7 - Booking Completion:
- DO NOT call get_stage_instructions_tool() in this stage (save function calls for booking)
- IMMEDIATELY call book_equipment_tool(equipment_id) to finalize the rental
- THEN: Speak directly to confirm all details (equipment, price, pickup location, etc.)
- FINALLY: Ask if they have any questions, then call end_conversation_tool()
- Say "Thank you for choosing Metro Equipment Rentals!" at the end
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
    logger.info(f"========================================")
    logger.info(f"INCOMING CALL - Entrypoint triggered")
    logger.info(f"Room: {ctx.room.name}")
    logger.info(f"========================================")
    
    # Create conversation state to track progress
    state = ConversationState()
    
    # Create disconnect event to wait for call end (like working example)
    disconnect_event = asyncio.Event()
    
    @ctx.room.on("disconnected")
    def on_room_disconnect(*args):
        logger.info("Room disconnected event received")
        disconnect_event.set()
    
    # Connect to room (telephony - audio only)
    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        logger.info("Connected to room")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return
    
    # Wait for participant to join (using working example pattern)
    logger.info(f"Participants in room: {len(ctx.room.remote_participants)}")
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")
    
    # Load equipment data (with cache, should be fast)
    logger.info("Loading equipment inventory...")
    try:
        available_equipment = get_available_equipment()
        logger.info(f"Equipment loaded successfully: {len(available_equipment)} items")
    except Exception as e:
        logger.error(f"Failed to load equipment: {e}")
        available_equipment = []
    
    # Format equipment list for better LLM readability
    equipment_text = []
    for item in available_equipment:
        equipment_text.append(
            f"- {item.get('Equipment ID')}: {item.get('Equipment Name', 'N/A')} "
            f"[Category: {item.get('Category')}, Daily Rate: ${item.get('Daily Rate')}, Status: {item.get('Status')}]"
        )
    formatted_equipment = "\n".join(equipment_text)
    
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

AVAILABLE EQUIPMENT (Total: {len(available_equipment)} items):
{formatted_equipment}

       IMPORTANT: You have access to these tools to help customers:
       - get_current_stage_tool() - Check which stage you're in
       - get_stage_instructions_tool() - Get detailed instructions for current stage
       - move_to_next_stage_tool() - Move to the next stage when ready
       - verify_business_license_tool(license_number) - Verify customer's business license
       - get_equipment_details_tool(equipment_id) - Get details about specific equipment
       - negotiate_price_tool(equipment_id, action) - Negotiate pricing ("offer_discount" to lower price, "accept_price" when agreed)
       - verify_site_safety_tool(job_address, equipment_category, weight_class) - Verify job site safety
       - verify_operator_credentials_tool(operator_license, certification_type) - Verify operator credentials
       - verify_insurance_coverage_tool(policy_number, required_amount, equipment_value) - Verify insurance
       - book_equipment_tool(equipment_id) - Book equipment and finalize rental
       - end_conversation_tool() - End the conversation when rental is complete or customer is done

WORKFLOW INSTRUCTIONS:
- You MUST complete stages ONE AT A TIME in order (1→2→3→4→5→6→7)
- NEVER skip ahead or ask for information from future stages
- After moving to a NEW stage with move_to_next_stage_tool(), call get_stage_instructions_tool() ONCE to see what to do
- Follow the stage instructions EXACTLY - only do what that stage says
- Call move_to_next_stage_tool() ONLY when the current stage is complete
- Stage 4 is PRICING NEGOTIATION (not operator credentials)
- Stage 5 is OPERATOR CERTIFICATION (ask for certification number)
- Stage 6 is INSURANCE VERIFICATION (ask for policy number)
- Stage 7: DO NOT call get_stage_instructions_tool(), just book immediately
- Be efficient with tool calls to avoid hitting function call limits
- Be friendly and professional throughout the conversation
- Confirm details by repeating them back to the customer

       CRITICAL TOOL CALLING RULES:
       - You MUST actually call the tools using function calls, not just describe calling them
       - DO NOT say "Calling tool..." and then make up a response
       - WAIT for the actual tool response before telling the customer the result
       - The tool will return the actual result - use that exact result in your response
       - Example: Call verify_business_license_tool(123), WAIT for response, then tell customer the result

       PRICING NEGOTIATION STRATEGY (Stage 4):
       - Quote ONLY the daily rate to the customer: "The daily rate is $X per day"
       - NEVER mention minimum rate or max rate to the customer
       - When customer objects to price or wants discount:
         1. Call negotiate_price_tool(equipment_id, "offer_discount")
         2. Tool returns a lower price - present it naturally to customer
         3. Repeat if customer still wants lower, until they accept or you hit minimum
       - When customer accepts a price (says yes/ok/sounds good/that works):
         1. Call negotiate_price_tool(equipment_id, "accept_price") to lock it in
         2. Tool will tell you to call move_to_next_stage_tool()
       - Be conversational and persuasive - don't immediately drop to minimum
       - The tool handles all calculations - you just present prices and read customer reactions

ENDING THE CONVERSATION:
- After completing Stage 7 (booking), call end_conversation_tool() to close the session
- If customer says "goodbye", "I'm done", "that's all", or similar, call end_conversation_tool()
- If customer decides not to rent (cancels), call end_conversation_tool()

CRITICAL GREETING REQUIREMENT: You MUST start EVERY phone call by greeting the customer immediately. When the call connects, respond with: "Hello! Thank you for calling Metro Equipment Rentals. I'm here to help you with your construction equipment rental needs. How can I assist you today?" Then proceed with the 7-stage workflow. Speak clearly and professionally for phone conversation.
"""
    
    logger.info(f"Loaded {len(available_equipment)} available equipment items (formatted for LLM)")
    
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
    # Configure to prevent self-interruption
    agent = Agent(
        instructions=initial_prompt,
        tools=tools,
        allow_interruptions=True,  # Allow user to interrupt
        min_endpointing_delay=1.0,  # Wait 1 second of silence before processing (prevents self-interrupt)
    )
    
    logger.info(f"Voice agent created and configured with {len(tools)} tools")
    logger.info(f"[PROMPT CHECK] System prompt length: {len(initial_prompt)} characters")
    logger.info(f"[PROMPT CHECK] Equipment count in prompt: {len(available_equipment)} items")
    logger.info(f"[PROMPT CHECK] First 200 chars of prompt: {initial_prompt[:200]}...")
    
    # Create OpenAI LLM instance
    # The @function_tool decorator should register tools globally and make them available to ANY LLM instance created

    openai_llm = livekit.plugins.openai.LLM(model="gpt-4o")
    
    logger.info("Created OpenAI LLM instance with gpt-4o model")
    
    # Create AgentSession with STT, LLM, TTS
    # VOICE MODE ENABLED for phone calls and production use
    logger.info("Initializing voice-enabled agent session...")
    logger.info(f"STT: deepgram/nova-2 (enabled for voice)")
    logger.info(f"TTS: openai/tts-1 (enabled for voice)")
    
    # VOICE MODE ENABLED - Using Deepgram (streaming) + OpenAI TTS
    # Switched back to OpenAI TTS due to ElevenLabs websocket issues on Railway
    
    # Add STT event handler to log what the agent is hearing
    def on_stt_transcript(transcript):
        logger.info(f"[STT HEARD] Customer said: '{transcript.text}'")
    
    deepgram_stt = livekit.plugins.deepgram.STT(
        model="nova-2",
        api_key=config.DEEPGRAM_API_KEY
    )
    
    # Use Deepgram for BOTH STT and TTS (best for real-time telephony)
    deepgram_tts = livekit.plugins.deepgram.TTS(
        api_key=config.DEEPGRAM_API_KEY
    )
    
    session = AgentSession(
        stt=deepgram_stt,  # Deepgram streaming STT
        llm=openai_llm,  # OpenAI GPT-4o
        tts=deepgram_tts,  # Deepgram TTS - ultra-low latency for telephony
    )
    
    logger.info("Voice-enabled agent session created with Deepgram STT + Deepgram TTS")
    
    # Add event listener for user speech (to log what STT transcribed)
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, *args):
        if track.kind == "audio":
            logger.info("[AUDIO] User audio track subscribed")
    
    # Start the session with the agent and room
    logger.info("Starting agent session")
    
    # Start the agent session (this will block until call ends)
    logger.info(f"[CONFIG] STT: Deepgram nova-2 | TTS: Deepgram | LLM: GPT-4o")
    logger.info(f"[EQUIPMENT] {len(available_equipment)} items loaded")
    logger.info("Starting agent session...")
    
    try:
        # Start session with correct parameters (agent + room)
        await session.start(agent=agent, room=ctx.room)
        logger.info("Agent session started - waiting for call to end")
        
        # Wait until the room is disconnected
        await disconnect_event.wait()
        logger.info("Call ended - disconnect event received")
        
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        await asyncio.sleep(0.5)
        logger.info("Cleanup complete - ready for next call")
        logger.info("="*60)



if __name__ == "__main__":
    # Configure logging for better debugging (like the working example)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting equipment rental telephony agent...")
    
    # Run the agent - match the working example's simple pattern
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="agent"  # This must match your dispatch rule
    ))

