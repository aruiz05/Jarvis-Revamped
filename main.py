from canvas_client import fetch_calendar_feed, parse_calendar_feed


def main() -> None:
    print("Canvas Calendar Reminder")
    print("Loading Canvas calendar...")
    print()

    # fetch and parse the canvas feed
    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
    except RuntimeError as error:
        print(error)
        return

    print("Canvas calendar loaded successfully.")
    print()

    # stop cleanly when the feed has no events
    if not events:
        print("No Canvas calendar items found.")
        return

    print(f"Canvas calendar items: {len(events)}")
    print()

    # show a readable summary for each item
    for index, event in enumerate(events, start=1):
        title = event.get("summary") or "Untitled Canvas calendar item"

        print(f"{index}. {title}")
        print(f"   Start: {_format_value(event.get('start'))}")
        print(f"   End: {_format_value(event.get('end'))}")
        print(f"   UID: {_format_value(event.get('uid'))}")
        print()


def _format_value(value: object) -> str:
    # show missing fields clearly
    if value is None:
        return "Not provided"
    return str(value)


if __name__ == "__main__":
    main()
