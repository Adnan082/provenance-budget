"""Assigns the six-way Role taxonomy to tool arguments. FROZEN after week 3 — see
CLAUDE.md rule 3.

DRAFT: `_ROLE_TABLE` below is a first pass over every LLM-supplied argument of
AgentDojo v1's 74 tools (banking, calendar, cloud_drive, email, file_reader, slack,
travel, user_account, web — agentdojo==0.1.35), assigned by the working definitions in
the module docstring below each suite. It is a hypothesis for the week-2
annotation-agreement pass CLAUDE.md's milestone table requires (κ measured against a
second annotator), not validated ground truth — do not treat it as oracle labels.

Framework-injected dependencies (the `Annotated[..., Depends(...)]` parameters
AgentDojo wires up itself, e.g. `account`, `inbox`, `calendar`) are excluded: the agent
never supplies them, so they carry no attacker-influenceable provenance and aren't
taint-tracked arguments in this project's sense.

Working definitions used to assign roles:
  target      — identifies who/where the action's effect lands (recipient, url,
                channel, participant, booking target).
  command     — selects what operation/instruction is carried out. Rare in this tool
                set: AgentDojo's tools are single-purpose REST-style calls, not
                command/shell/SQL executors, so most "what to do" is fixed by which
                tool was called, not by an argument. Reserved for the few arguments
                that are genuinely instruction-like.
  credential  — secrets or account identifiers used for authentication (password,
                IBAN).
  content     — the payload being moved or written, not the destination.
  selector    — which existing record to read, filter, or act on (ids, queries,
                filenames, counts).
  control     — flow-control/timing/permission toggles that affect how an allowed
                action executes, without changing its destination or payload.
"""
from __future__ import annotations

from pb.trace.schema import Role

_ROLE_TABLE: dict[tuple[str, str], Role] = {
    # --- banking (BankAccount injected as `account`) ---
    ("get_most_recent_transactions", "n"): "selector",
    ("schedule_transaction", "recipient"): "target",
    ("schedule_transaction", "amount"): "content",
    ("schedule_transaction", "subject"): "content",
    ("schedule_transaction", "date"): "control",
    ("schedule_transaction", "recurring"): "control",
    ("send_money", "recipient"): "target",
    ("send_money", "amount"): "content",
    ("send_money", "subject"): "content",
    ("send_money", "date"): "control",
    ("set_balance", "balance"): "content",
    ("set_iban", "iban"): "credential",
    ("update_scheduled_transaction", "id"): "selector",
    ("update_scheduled_transaction", "recipient"): "target",
    ("update_scheduled_transaction", "amount"): "content",
    ("update_scheduled_transaction", "subject"): "content",
    ("update_scheduled_transaction", "date"): "control",
    ("update_scheduled_transaction", "recurring"): "control",
    # --- calendar (Calendar as `calendar`, Inbox as `inbox`) ---
    ("add_calendar_event_participants", "event_id"): "selector",
    ("add_calendar_event_participants", "participants"): "target",
    ("cancel_calendar_event", "event_id"): "selector",
    ("create_calendar_event", "title"): "content",
    ("create_calendar_event", "start_time"): "control",
    ("create_calendar_event", "end_time"): "control",
    ("create_calendar_event", "description"): "content",
    ("create_calendar_event", "participants"): "target",
    ("create_calendar_event", "location"): "content",
    ("get_day_calendar_events", "day"): "selector",
    ("reschedule_calendar_event", "event_id"): "selector",
    ("reschedule_calendar_event", "new_start_time"): "control",
    ("reschedule_calendar_event", "new_end_time"): "control",
    ("search_calendar_events", "query"): "selector",
    ("search_calendar_events", "date"): "selector",
    # --- cloud_drive (CloudDrive as `cloud_drive`) ---
    ("append_to_file", "file_id"): "selector",
    ("append_to_file", "content"): "content",
    ("create_file", "filename"): "content",
    ("create_file", "content"): "content",
    ("delete_file", "file_id"): "selector",
    ("get_file_by_id", "file_id"): "selector",
    ("search_files", "query"): "selector",
    ("search_files_by_filename", "filename"): "selector",
    ("share_file", "file_id"): "selector",
    ("share_file", "email"): "target",
    ("share_file", "permission"): "control",
    # --- email (Inbox as `inbox`) ---
    ("delete_email", "email_id"): "selector",
    ("search_contacts_by_email", "query"): "selector",
    ("search_contacts_by_name", "query"): "selector",
    ("search_emails", "query"): "selector",
    ("search_emails", "sender"): "selector",
    ("send_email", "recipients"): "target",
    ("send_email", "subject"): "content",
    ("send_email", "body"): "content",
    ("send_email", "attachments"): "content",
    ("send_email", "cc"): "target",
    ("send_email", "bcc"): "target",
    # --- file_reader (Filesystem as `filesystem`) ---
    ("read_file", "file_path"): "selector",
    # --- slack (Slack as `slack`) ---
    ("add_user_to_channel", "user"): "target",
    ("add_user_to_channel", "channel"): "target",
    ("get_users_in_channel", "channel"): "selector",
    ("invite_user_to_slack", "user"): "target",
    ("invite_user_to_slack", "user_email"): "target",
    ("read_channel_messages", "channel"): "selector",
    ("read_inbox", "user"): "selector",
    ("remove_user_from_slack", "user"): "target",
    ("send_channel_message", "channel"): "target",
    ("send_channel_message", "body"): "content",
    ("send_direct_message", "recipient"): "target",
    ("send_direct_message", "body"): "content",
    # --- travel (Restaurants/CarRental/Hotels/Flights/Reservation/User injected) ---
    ("check_restaurant_opening_hours", "restaurant_names"): "selector",
    ("get_all_car_rental_companies_in_city", "city"): "selector",
    ("get_all_hotels_in_city", "city"): "selector",
    ("get_all_restaurants_in_city", "city"): "selector",
    ("get_car_fuel_options", "company_name"): "selector",
    ("get_car_price_per_day", "company_name"): "selector",
    ("get_car_rental_address", "company_name"): "selector",
    ("get_car_types_available", "company_name"): "selector",
    ("get_contact_information_for_restaurants", "restaurant_names"): "selector",
    ("get_cuisine_type_for_restaurants", "restaurant_names"): "selector",
    ("get_dietary_restrictions_for_all_restaurants", "restaurant_names"): "selector",
    ("get_flight_information", "departure_city"): "selector",
    ("get_flight_information", "arrival_city"): "selector",
    ("get_hotels_address", "hotel_name"): "selector",
    ("get_hotels_prices", "hotel_names"): "selector",
    ("get_price_for_restaurants", "restaurant_names"): "selector",
    ("get_rating_reviews_for_car_rental", "company_name"): "selector",
    ("get_rating_reviews_for_hotels", "hotel_names"): "selector",
    ("get_rating_reviews_for_restaurants", "restaurant_names"): "selector",
    ("get_restaurants_address", "restaurant_names"): "selector",
    ("reserve_car_rental", "company"): "target",
    ("reserve_car_rental", "start_time"): "control",
    ("reserve_car_rental", "end_time"): "control",
    ("reserve_hotel", "hotel"): "target",
    ("reserve_hotel", "start_day"): "control",
    ("reserve_hotel", "end_day"): "control",
    ("reserve_restaurant", "restaurant"): "target",
    ("reserve_restaurant", "start_time"): "control",
    # --- user_account (UserAccount as `account`) ---
    ("update_password", "password"): "credential",
    ("update_user_info", "first_name"): "content",
    ("update_user_info", "last_name"): "content",
    ("update_user_info", "street"): "content",
    ("update_user_info", "city"): "content",
    # --- web (Web as `web`) ---
    ("download_file", "url"): "target",
    ("download_file", "file_name"): "content",
    ("get_webpage", "url"): "target",
    ("post_webpage", "url"): "target",
    ("post_webpage", "content"): "content",
}


class RoleNotAssigned(KeyError):
    """Raised when (tool, param) has no entry in the draft table. Deliberately loud —
    silently guessing a role via a naming heuristic would be exactly the kind of
    invented, unreviewed ground truth CLAUDE.md's 'Ground truth' section warns against."""


def assign_role(tool: str, param: str) -> Role:
    try:
        return _ROLE_TABLE[(tool, param)]
    except KeyError:
        raise RoleNotAssigned(f"{tool}({param}) has no draft role assignment") from None
