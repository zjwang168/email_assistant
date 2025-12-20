
import json
import os
from services.llm_extractor import build_forward_package
from services.calendar_generator import detect_event_and_build_ics, build_ics_from_calendar_event

# Mock text provided by user
subject = "Fwd: Costello, CEHD, CVPA, Schar Degree Celebration - Know Before You Go! – Key Info"
body = """
Costello, CEHD, CVPA, Schar Degree Celebration

Thursday, December 18, 2025

 
Dear Guest, 

 

We look forward to welcoming you to the Costello, CEHD, CVPA, Schar Degree Celebration on Thursday, December 18th at 6:30 pm at EagleBank Arena! Please review the important information below to ensure a smooth and enjoyable experience. 

Tickets & Entry 

Guests should bring the ticket(s) sent to them by their graduating student. Tickets may be: 

Added to an Apple or Google Wallet 

Printed out

Displayed from the email containing the QR code at check-in 

Each ceremony has its own unique tickets. 

 

To enter the arena, guests must present a ticket that matches the specific ceremony they are attending. Tickets for a different ceremony, regardless of day or time, will not be accepted at the doors. Please double-check that you have the correct tickets before arriving. 

Doors open one hour prior to the start of the ceremony, and we strongly encourage arriving at that time to allow for parking, entry, and seating. 

Parking 

Complimentary parking will be available in Lots A, C, and K for all ceremonies. Please expect heavy traffic on and around the Fairfax Campus, especially along Braddock Road. Drivers should follow campus signage and traffic controls. 

 

Accessible Parking 

Accessible parking is located in Lot A, near the south entrance to EagleBank Arena. To access these spaces, please use the Roanoke River Road and Nottoway River Lane entrances from Braddock Road. 

 

Security & Venue Policies 

To help expedite entry: 

All guests will pass through a security weapons detection monitor. 
If you must bring a bag, it must comply with venue policies. 
Please review the prohibited items list and full venue policies in advance: 

Venue Policies: https://www.eaglebankarena.com/plan-your-visit/arena-policies 

Accessibility Information 

ASL & Captioning 

ASL interpretation and closed captioning will be provided. 

 

Accessible Seating 

Easy-access seating is available in Rows E, F, and G on the concourse level. These sections do not require stairs and are marked as reserved for guests with special needs. 

No advance notice or reservation is required. 

One companion may accompany each guest requiring assistance. 

Ushers are stationed at every portal to assist. 

 

Wheelchair Seating 

Wheelchair-accessible seating is available at portals 4, 8, 13, and 17. Ushers will be present to help. 

We look forward to celebrating this momentous occasion with you. Thank you for reviewing these details and planning ahead. We can’t wait to see you at the ceremony! 

GMU Graduation Website
"""

print("--- Testing build_forward_package ---")
forward_pkg = build_forward_package(subject, body)
print(json.dumps(forward_pkg, indent=2))

print("\n--- Testing Calendar Logic ---")
ics_content = None
if forward_pkg.get("has_calendar_event") and forward_pkg.get("calendar_event"):
    print("Using LLM calendar event")
    ics_content = build_ics_from_calendar_event(forward_pkg["calendar_event"])

if not ics_content:
    print("Fallback to heuristic calendar event")
    ics_content = detect_event_and_build_ics(subject, body)

print("\nICS Content:")
print(ics_content)
