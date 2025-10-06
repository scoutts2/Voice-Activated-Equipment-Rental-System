# Voice-Activated Equipment Rental System - Technical Assignment 

## Business Background

You work for a growing construction equipment rental company that handles dozens of phone calls daily from contractors needing heavy machinery. Currently, your staff manually processes each rental call, which takes 20-30 minutes per customer and requires checking multiple systems, making verification calls, and updating inventory records.

Your company wants to automate this process with a smart voice system that can handle these inbound calls just like your experienced rental agents do. When contractors call your main number, the system should guide them through the complete rental process - from verifying their credentials to booking equipment and updating your inventory.

The conversation needs to feel natural, allowing customers to ask questions, negotiate pricing, and get equipment recommendations. Most importantly, the system must maintain all your business requirements and safety standards while processing rentals efficiently.

## Current Business Process

When a contractor calls today, here's what happens:

**Step 1**: Verify their business license and check if they're an approved customer
**Step 2**: Help them find the right equipment from your available inventory  
**Step 3**: Confirm they can meet the operational requirements for the equipment
**Step 4**: Negotiate pricing within your rate boundaries
**Step 5**: Verify their equipment operator has proper certifications
**Step 6**: Check their insurance coverage meets minimum requirements
**Step 7**: Complete the booking and update inventory records

Your team maintains equipment inventory, customer approvals, and operator certifications in spreadsheets shared through Google Drive or Google Sheets. These get updated throughout the day as equipment is rented out and returned.

## Technical Challenge

Build a voice conversation system using the LiveKit Agents framework that can handle the complete rental workflow. The system should process inbound calls, maintain conversation context throughout multiple verification steps, integrate with your Google Drive/Google Sheets data, and complete bookings while updating inventory in real-time.

## Technical Requirements

### Voice Conversation System Architecture

Design your system with specialized conversation handlers for each workflow stage. Each stage should focus on specific business requirements while maintaining natural conversation flow. Your system needs to track progress through the workflow and determine appropriate next steps based on verification results and customer responses.

### Google Drive/Google Sheets Integration

Your equipment inventory lives in a Google Drive CSV file or Google Sheets that your team updates continuously. Your voice system needs to read this data to show available equipment, check requirements, and update equipment status when bookings are completed. Handle concurrent access scenarios where multiple customers might be interested in the same equipment.

### External Verification Integration

While your CSV/Sheets contains equipment details, you also need to verify information through external services. Implement placeholder functions for these verification calls:

**verify_business_license(license_number)**
- **Data from User**: `license_number` - collected during conversation when customer provides their business license
- **Data from CSV**: None - this function checks external government databases
- **Purpose**: Check license validity with state authorities

**verify_operator_credentials(operator_license, certification_type)**
- **Data from User**: `operator_license` - collected when customer provides their operator's certification number
- **Data from CSV**: `certification_type` - pulled from "Operator Cert Required" field of selected equipment
- **Purpose**: Confirm operator certifications with licensing boards
- **Example**: Customer selects Liebherr crane → CSV shows "Crane Operator License" required → verify their operator's license is specifically for crane operation

**verify_site_safety(job_address, equipment_category, weight_class)**
- **Data from User**: `job_address` - collected when customer provides their job site location
- **Data from CSV**: 
  - `equipment_category` - from "Category" field of selected equipment
  - `weight_class` - from "Weight Class" field of selected equipment
- **Purpose**: Validate job site safety requirements
- **Example**: Customer selects Super Heavy crane → verify job site can handle heavy equipment access and ground conditions

**verify_insurance_coverage(policy_number, required_amount, equipment_value)**
- **Data from User**: `policy_number` - collected when customer provides their insurance policy details
- **Data from CSV**: 
  - `required_amount` - from "Min Insurance" field of selected equipment
  - `equipment_value` - estimated from "Daily Rate" and replacement cost calculations
- **Purpose**: Confirm insurance policy details
- **Example**: Customer selects $4,500/day crane → CSV shows $8,000,000 minimum coverage → verify their policy meets this requirement

These functions should return true by default for your implementation, but design your system to handle both success and failure scenarios as if these were real external service calls.

### Workflow Stages and Business Logic

**Stage 1 - Customer Verification**
Collect business license number and verify against your approved customers. Call external license verification service to confirm current validity. Only proceed if both internal approval and external verification pass.

**Stage 2 - Equipment Discovery** 
Present available equipment from your CSV inventory (status="AVAILABLE" only). Handle natural language requests like "I need something for digging" or "show me forklifts under $400". Let customers browse options and select specific equipment.

Customers don't speak in database terms - they use natural language like:
- "I'm digging a basement, what do you have?"
- "Need something to move pallets around the warehouse"  
- "Looking for equipment to lift heavy beams to the second floor"
- "What's good for grading a parking lot?"
- "I need to demolish a small building"
- "Something under $500 a day that can handle 20,000 pounds"

Pass the complete CSV equipment data as context to your conversation system. Let the LLM/prompt logic interpret customer requests and match them to appropriate equipment based on the full context of equipment_name, category, and specifications. Don't try to program exact keyword matching - let the conversational AI understand intent and suggest relevant options.

**Stage 3 - Requirements Confirmation**
Verify customer can meet operational requirements for selected equipment. Check operator certification requirements, equipment weight class restrictions, and job site safety standards through external verification calls.

**Stage 4 - Pricing Negotiation**
Present equipment daily rate and handle price negotiations. Stay within minimum (daily_rate) and maximum (max_negotiable_rate) boundaries from your CSV data. Track negotiation attempts and reach agreement or appropriately end discussions.

**Stage 5 - Operator Certification**
Collect operator details and verify certifications match equipment requirements exactly. Cross-reference against your operator database and confirm current status through external certification authority checks.

**Stage 6 - Insurance Verification** 
Verify customer insurance meets minimum coverage requirements for selected equipment. Check policy details through external insurance verification services and ensure adequate protection for equipment value.

**Stage 7 - Booking Completion**
Finalize rental by updating equipment status in your CSV from "AVAILABLE" to "RENTED". Generate booking confirmation with pickup details, operator requirements, and rental terms.

### Success and Failure Conditions

Each stage has specific conditions for proceeding or ending the call:
- **Proceed**: All verifications pass and requirements are met
- **End Call**: Customer fails verification, cannot meet requirements, negotiation fails, or system errors occur

Your system should handle both successful bookings and various failure scenarios gracefully, providing clear explanations and maintaining professional tone throughout.

## Data Consistency Requirements - Simplified Approach

### Race Condition Handling

Your CSV integration should be primarily read-only throughout most of the conversation. The only critical point where you need to handle concurrent access is during the final booking step.

### Implementation Approach

**During Conversation (Stages 1-6)**: Read equipment data from CSV without any locking or reservation. Multiple customers can simultaneously discuss the same equipment.

**Final Booking Check (Stage 7)**: Right before completing the booking, perform one atomic check-and-update operation:

1. **Read Current Status**: Check if the equipment status is still "AVAILABLE"
2. **Immediate Update**: If available, immediately update status to "RENTED"
3. **Handle Race Condition**: If status shows "RENTED", inform customer it was just booked

This approach keeps your system simple while handling the one critical race condition. You don't need complex reservation systems or distributed locking - just one final atomic check before updating the CSV status field.

The key is performing this check as late as possible in the workflow, right before the final status update, to minimize the window where race conditions can occur.

## CSV Data Points - Business Context & Placeholder Function Alignment

### Equipment Identification & Basic Info
- **Equipment ID**: Internal tracking number for inventory management and booking systems
- **Equipment Name**: What customers recognize - "CAT 320D" means something to contractors who know that's a reliable mid-size excavator
- **Category**: How customers think about equipment - "I need lifting equipment" vs "I need earthmoving equipment"
- **Storage Location**: Matters for pickup logistics - contractors prefer equipment closer to their job sites

### Financial Data Points
- **Daily Rate**: Your starting negotiation point - what you'd like to get for the equipment
- **Max Rate**: Your absolute ceiling - you cannot rent above this even if customer offers more (covers your costs, insurance, profit margins)
- **Status**: Critical for availability - "RENTED" means another customer has it, "MAINTENANCE" means it's broken, "AVAILABLE" means ready to rent

### Safety & Compliance Requirements  
- **Operator Cert Required**: Legal requirement - specific license types for different equipment (crane operators need different training than forklift operators)
- **Min Insurance**: Risk management - heavier/more expensive equipment needs higher coverage to protect your business
- **Weight Class**: Determines site requirements - "Super Heavy" equipment needs reinforced ground, special transport, wider access routes

### Placeholder Functions - Proper Alignment

**verify_business_license(license_number)**
- **Business Context**: Check if customer's business license is valid with state authorities
- **CSV Alignment**: Not directly related to equipment CSV - this checks external government databases
- **Business Need**: Ensures you're renting to legitimate businesses, not fly-by-night operators

**verify_operator_credentials(operator_license, certification_type)**
- **Business Context**: Verify operator has valid certification for specific equipment type
- **CSV Alignment**: `certification_type` should match the "Operator Cert Required" field from selected equipment
- **Example**: If customer selects Liebherr crane (requires "Crane Operator License"), verify their operator actually has that specific certification
- **Business Need**: Legal compliance and safety - wrong operator type could cause accidents or legal liability

**verify_site_safety(job_address, equipment_category, weight_class)**
- **Business Context**: Confirm job site can safely accommodate the equipment
- **CSV Alignment**: 
  - `equipment_category` from "Category" field (Heavy Excavation, Lifting Equipment, etc.)
  - `weight_class` from "Weight Class" field (Super Heavy equipment needs special site prep)
- **Example**: Super Heavy crane needs strong ground, overhead clearance, proper access roads
- **Business Need**: Prevent equipment damage, site accidents, and liability issues

**verify_insurance_coverage(policy_number, required_amount, equipment_value)**
- **Business Context**: Confirm customer's insurance covers potential equipment damage/loss
- **CSV Alignment**: 
  - `required_amount` from "Min Insurance" field for selected equipment
  - `equipment_value` can be estimated from daily rate and replacement cost
- **Example**: Manitowoc crane requires $8,000,000 coverage - customer with $2,000,000 policy cannot rent it
- **Business Need**: Protect your investment - if equipment gets damaged, insurance covers replacement

## Sample Call Transcripts with Tool Calls and CSV Data

### Successful Booking Scenario

**System**: Hello, you've reached Metro Equipment Rentals. How can I help you today?

**Customer**: Hi, I need an excavator for a foundation job next week.

**System**: I can help with that. First, let me verify your business credentials. Can you provide your business license number?

**Customer**: Sure, it's BL782341.

**System**: Let me confirm - B-L-7-8-2-3-4-1, correct?

**Customer**: Yes, that's right.

*[TOOL CALL: verify_business_license("BL782341") → returns True]*

**System**: Perfect. I have you verified as Metro Construction LLC, and your account is in good standing. For foundation work, I have several excavators available. 

*[CSV READ: Filter equipment where Category="Heavy Excavation" AND Status="AVAILABLE"]*
*[CSV DATA: EQ001 (CAT 320D, $1850), EQ008 (Hitachi ZX350, $2200), EQ013 (Komatsu PC390, $2400)]*

There's a CAT 320D at $1,850 per day, a Hitachi ZX350 at $2,200 per day, and a Komatsu PC390 at $2,400 per day. What size foundation are you working on?

**Customer**: About 3,000 square feet. What would you recommend?

**System**: For that size job, the Hitachi ZX350 would be perfect. It's $2,200 per day and located at our North Yard. Does that sound good?

**Customer**: The Hitachi works, but can you do better on the price? I need it for 5 days.

*[CSV READ: EQ008 - Daily Rate: $2200, Max Rate: $2600]*

**System**: For a 5-day rental, I could do $2,100 per day. Would that work for your budget?

**Customer**: That's much better. Let's go with $2,100 per day.

**System**: Excellent. Now I need to verify some operational requirements. The operator will need a Heavy Equipment Class A certification. Do you have someone with that license?

*[CSV READ: EQ008 - Operator Cert Required: "Heavy Equipment Class A"]*

**Customer**: Yes, Robert Chen has his Class A license - certificate OC445123.

**System**: Great. What's your job site address so I can verify safety requirements?

**Customer**: 1247 Industrial Boulevard downtown.

*[TOOL CALL: verify_site_safety("1247 Industrial Boulevard", "Heavy Excavation", "Heavy") → returns True]*
*[CSV DATA: Equipment Category="Heavy Excavation", Weight Class="Heavy"]*

**System**: Perfect. Now for insurance - this equipment requires $2,800,000 minimum coverage. What's your policy number?

*[CSV READ: EQ008 - Min Insurance: $2800000]*

**Customer**: INS-447821 with Builders Insurance Group.

*[TOOL CALL: verify_insurance_coverage("INS-447821", "2800000", "220000") → returns True]*
*[CSV DATA: Min Insurance=$2800000, Equipment Value estimated from Daily Rate]*

**System**: Excellent, your coverage meets our requirements. What's Robert's contact number?

**Customer**: 555-987-6543.

*[TOOL CALL: verify_operator_credentials("OC445123", "Heavy Equipment Class A") → returns True]*
*[USER DATA: operator_license="OC445123", CSV DATA: certification_type="Heavy Equipment Class A"]*

**System**: Perfect - 5-5-5-9-8-7-6-5-4-3, correct? All set! I've booked the Hitachi ZX350 for 5 days at $2,100 per day, total $10,500. Pickup is at our North Yard. You'll get confirmation details by email. Anything else I can help with?

*[CSV UPDATE: EQ008 Status changed from "AVAILABLE" to "RENTED"]*

**Customer**: That covers everything, thanks!

### Failed Negotiation Scenario

**System**: Hello, you've reached Metro Equipment Rentals. How can I help you today?

**Customer**: I need your biggest crane for a major lift job.

**System**: I can help with that. Let me verify your credentials first. Business license number?

**Customer**: BL782341.

*[TOOL CALL: verify_business_license("BL782341") → returns True]*

**System**: Metro Construction, verified. Our largest crane is the Manitowoc 16000 Crawler Crane at $4,500 per day. It handles up to 160 tons. Will that work for your project?

*[CSV READ: Filter by Category="Lifting Equipment", find largest by capacity]*
*[CSV DATA: EQ011 - Daily Rate: $4500, Max Rate: $5200]*

**Customer**: The capacity is perfect, but $4,500 is way over budget. I was thinking more like $3,500.

*[CSV READ: EQ011 - Daily Rate: $4500 (customer offer $3500 is below minimum)]*

**System**: I understand budget is important. Let me see what I can do... I could bring it down to $4,200 per day, but that's about as low as I can go on this equipment.

**Customer**: That's still too high. My absolute maximum is $3,800.

*[BUSINESS LOGIC: $3800 < Daily Rate $4500, cannot accept]*

**System**: I'm sorry, but I can't go that low on the crawler crane. The equipment costs and maintenance don't allow us to rent below $4,200. Would you consider our smaller Liebherr mobile crane at $3,200 per day? It handles up to 70 tons.

*[CSV READ: EQ003 - Liebherr crane Daily Rate: $3200]*

**Customer**: No, I really need the 160-ton capacity. I'll have to look elsewhere.

**System**: I understand. I'll keep your information on file for future projects. Have a good day.

### Equipment Unavailable Scenario  

**System**: Hello, you've reached Metro Equipment Rentals. How can I help you today?

**Customer**: I need an excavator for tomorrow morning.

**System**: Let me check availability after verifying your credentials. Business license number?

**Customer**: BL445892.

*[TOOL CALL: verify_business_license("BL445892") → returns True]*

**System**: Citywide Builders, verified. Let me check excavator availability...

*[CSV READ: Filter Category="Heavy Excavation" AND Status="AVAILABLE"]*
*[CSV RESULT: No equipment with Status="AVAILABLE" - all show "RENTED"]*

I'm sorry, but all our excavators are currently rented out. The earliest availability would be Thursday when equipment returns.

**Customer**: I really need something tomorrow for utility trenching.

**System**: I understand the urgency. For trenching work, you really do need an excavator. Unfortunately, I don't have anything suitable available tomorrow. Should I reserve the CAT 320D for Thursday?

**Customer**: No, I need to complete this tomorrow. I'll try elsewhere.

**System**: Sorry we couldn't help this time. Please keep us in mind for future projects. 

### Race Condition Scenario

**System**: Excellent. Now let me finalize your booking for the CAT 320D Excavator...

*[CSV READ: Check EQ001 status before final booking]*
*[CSV RESULT: Status changed from "AVAILABLE" to "RENTED" by another customer]*

**System**: Uh oh! I'm sorry, but that excavator just got booked by another customer while we were talking. Let me show you the alternatives - I still have the Hitachi ZX350 available at $2,200 per day or the Komatsu PC390 at $2,400 per day. Both are similar capacity. Would either of those work for your project?

*[CSV READ: Check remaining Heavy Excavation equipment with Status="AVAILABLE"]*

**Customer**: That's frustrating! What about the Hitachi?

**System**: Let me check the Hitachi right now to make sure it's still available... 

*[CSV READ: Check EQ008 status in real-time]*
*[CSV RESULT: EQ008 Status="AVAILABLE"]*

**System**: Good news - the Hitachi ZX350 is still available. It's $2,200 per day, but since you had to switch equipment, I can offer it at the same $2,100 rate we agreed on for the CAT. Would that work?

**Customer**: Yes, let's book the Hitachi then.

**System**: Perfect. Let me secure that for you right now...

*[CSV UPDATE: EQ008 Status changed from "AVAILABLE" to "RENTED" atomically]*

**System**: Excellent! Your Hitachi ZX350 is now booked for 5 days at $2,100 per day. Pickup is at our North Yard...

## Basic Function Parameter Examples

```
# Example function calls with actual parameters:

verify_business_license("BL782341")
# User provided: "BL782341"
# CSV data: None

verify_operator_credentials("OC445123", "Heavy Equipment Class A") 
# User provided: "OC445123"
# CSV data: "Heavy Equipment Class A" (from selected equipment)

verify_site_safety("1247 Industrial Boulevard", "Heavy Excavation", "Heavy")
# User provided: "1247 Industrial Boulevard" 
# CSV data: "Heavy Excavation" (Category), "Heavy" (Weight Class)

verify_insurance_coverage("INS-447821", "2800000", "220000")
# User provided: "INS-447821"
# CSV data: "2800000" (Min Insurance), "220000" (estimated equipment value)
```

## Equipment Inventory Data Structure

Your Google Drive CSV or Google Sheets contains the following equipment information:

| Equipment ID | Equipment Name | Category | Daily Rate | Status | Operator Cert Required | Min Insurance | Storage Location | Max Rate | Weight Class |
|--------------|----------------|----------|------------|--------|----------------------|---------------|------------------|----------|--------------|
| EQ001 | CAT 320D Hydraulic Excavator | Heavy Excavation | 1850 | AVAILABLE | Heavy Equipment Class A | 2500000 | North Yard | 2200 | Medium Heavy |
| EQ002 | John Deere 644K Wheel Loader | Material Handling | 1200 | RENTED | Heavy Equipment Class B | 1500000 | South Yard | 1450 | Medium |
| EQ003 | Liebherr LTM 1070 Mobile Crane | Lifting Equipment | 3200 | AVAILABLE | Crane Operator License | 5000000 | North Yard | 3800 | Super Heavy |
| EQ004 | Toyota 8FGU25 Forklift | Warehouse Equipment | 280 | AVAILABLE | Forklift License | 500000 | Equipment Shed | 350 | Light |
| EQ005 | CAT D6T Bulldozer | Earthmoving | 2100 | MAINTENANCE | Heavy Equipment Class A | 3000000 | Service Bay | 2500 | Heavy |
| EQ006 | JLG 2630ES Scissor Lift | Access Equipment | 320 | AVAILABLE | Aerial Work Platform | 750000 | Equipment Shed | 380 | Light |
| EQ007 | Bobcat S770 Skid Steer | Compact Equipment | 450 | AVAILABLE | Skid Steer License | 800000 | South Yard | 550 | Medium |
| EQ008 | Hitachi ZX350 Excavator | Heavy Excavation | 2200 | AVAILABLE | Heavy Equipment Class A | 2800000 | North Yard | 2600 | Heavy |
| EQ009 | Genie Z-60 Boom Lift | Access Equipment | 480 | RESERVED | Aerial Work Platform | 1200000 | Equipment Shed | 580 | Medium |
| EQ010 | CAT 950M Wheel Loader | Material Handling | 1650 | AVAILABLE | Heavy Equipment Class B | 2000000 | South Yard | 1950 | Medium Heavy |
| EQ011 | Manitowoc 16000 Crawler Crane | Lifting Equipment | 4500 | AVAILABLE | Crane Operator License | 8000000 | North Yard | 5200 | Super Heavy |
| EQ012 | Yale GLP080 Forklift | Warehouse Equipment | 320 | AVAILABLE | Forklift License | 600000 | Equipment Shed | 390 | Light |
| EQ013 | Komatsu PC390 Excavator | Heavy Excavation | 2400 | AVAILABLE | Heavy Equipment Class A | 3200000 | North Yard | 2800 | Heavy |
| EQ014 | JCB 541-70 Telehandler | Material Handling | 380 | AVAILABLE | Telehandler License | 900000 | South Yard | 460 | Medium |
| EQ015 | CAT 140M Motor Grader | Road Construction | 1900 | AVAILABLE | Motor Grader License | 2200000 | North Yard | 2300 | Heavy |

### Data Usage Notes

- **Status**: Only show equipment marked "AVAILABLE" to customers. Hide "RENTED", "MAINTENANCE", "RESERVED"
- **Daily Rate**: Starting point for pricing discussions
- **Max Rate**: Absolute ceiling for negotiations - never exceed this amount
- **Operator Cert Required**: Must match customer's operator certification exactly
- **Min Insurance**: Customer's insurance must meet or exceed this amount
- **Storage Location**: Included in pickup instructions when booking is completed
- **Weight Class**: Determines additional safety and certification requirements

Your voice system should use this data to guide customers through equipment selection, verify requirements, negotiate within rate boundaries, and complete bookings by updating the status field when rentals are finalized.

## Note on External Verification Examples

*While the external verification functions (verify_business_license, verify_site_safety, verify_operator_credentials, verify_insurance_coverage) default to returning true in your implementation, in real scenarios they could fail and require call termination. For example:*

- *verify_business_license returns false → "Your license shows as expired in the state system. You'll need to renew before we can proceed."*
- *verify_operator_credentials returns false → "The certification authority shows this license as suspended. The operator would need to resolve this first."*
- *verify_site_safety returns false → "The site doesn't meet safety requirements for this equipment type. You'd need site modifications first."*

*These are just examples of what external failures would look like, but your placeholder functions should return true for the assignment.*

## Delivery Requirements

1. **Complete Voice System** - Implement all 7 workflow stages with natural conversation handling
2. **Google Drive/Google Sheets Integration** - Read inventory data and update equipment status for completed bookings
3. **External Verification Stubs** - Implement placeholder functions for all external service calls
4. **Error Handling** - Graceful handling of failed verifications, unavailable equipment, and system errors
5. **Documentation** - Explain your architectural decisions and conversation flow design
6. **Test Scenarios** - Demonstrate both successful bookings and various failure cases

Your system should feel like talking to an experienced rental agent while efficiently processing the complex verification and booking workflow behind the scenes. 
