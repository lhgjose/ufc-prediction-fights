"""HTML parsers for UFCStats.com pages."""

import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from .models import Event, Fight, FightStats, Fighter


def _extract_id_from_url(url: str) -> str:
    """Extract the ID from a UFCStats URL."""
    return url.rstrip("/").split("/")[-1]


def _parse_height(height_str: str) -> Optional[int]:
    """Parse height string like '6' 4"' to inches."""
    if not height_str or height_str == "--":
        return None
    match = re.match(r"(\d+)'\s*(\d+)\"?", height_str.strip())
    if match:
        feet, inches = int(match.group(1)), int(match.group(2))
        return feet * 12 + inches
    return None


def _parse_reach(reach_str: str) -> Optional[int]:
    """Parse reach string like '84"' to inches."""
    if not reach_str or reach_str == "--":
        return None
    match = re.match(r"(\d+)\"?", reach_str.strip())
    if match:
        return int(match.group(1))
    return None


def _parse_weight(weight_str: str) -> Optional[int]:
    """Parse weight string like '185 lbs.' to pounds."""
    if not weight_str or weight_str == "--":
        return None
    match = re.match(r"(\d+)", weight_str.strip())
    if match:
        return int(match.group(1))
    return None


def _parse_percentage(pct_str: str) -> Optional[float]:
    """Parse percentage string like '52%' to float 0.52."""
    if not pct_str or pct_str == "--":
        return None
    match = re.match(r"(\d+)%", pct_str.strip())
    if match:
        return int(match.group(1)) / 100.0
    return None


def _parse_float(val_str: str) -> Optional[float]:
    """Parse float string."""
    if not val_str or val_str == "--":
        return None
    try:
        return float(val_str.strip())
    except ValueError:
        return None


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string like 'January 18, 2025'."""
    if not date_str or date_str == "--":
        return None
    try:
        return datetime.strptime(date_str.strip(), "%B %d, %Y").date()
    except ValueError:
        pass
    # Try alternate format
    try:
        return datetime.strptime(date_str.strip(), "%b %d, %Y").date()
    except ValueError:
        return None


def _parse_record(record_str: str) -> tuple[int, int, int, int]:
    """Parse record string like '22-5-0 (1 NC)' to (wins, losses, draws, nc)."""
    wins, losses, draws, nc = 0, 0, 0, 0
    if not record_str:
        return wins, losses, draws, nc

    # Check for NC
    nc_match = re.search(r"\((\d+)\s*NC\)", record_str)
    if nc_match:
        nc = int(nc_match.group(1))

    # Parse main record
    main_match = re.match(r"(\d+)-(\d+)-(\d+)", record_str.strip())
    if main_match:
        wins = int(main_match.group(1))
        losses = int(main_match.group(2))
        draws = int(main_match.group(3))

    return wins, losses, draws, nc


def _parse_control_time(time_str: str) -> int:
    """Parse control time like '2:35' to seconds."""
    if not time_str or time_str == "--":
        return 0
    match = re.match(r"(\d+):(\d+)", time_str.strip())
    if match:
        minutes, seconds = int(match.group(1)), int(match.group(2))
        return minutes * 60 + seconds
    return 0


def _parse_strike_stats(stat_str: str) -> tuple[int, int]:
    """Parse strike stats like '45 of 89' to (landed, attempted)."""
    if not stat_str or stat_str == "--":
        return 0, 0
    match = re.match(r"(\d+)\s*of\s*(\d+)", stat_str.strip())
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _get_text(element: Optional[Tag]) -> str:
    """Safely extract text from element."""
    if element is None:
        return ""
    return element.get_text(strip=True)


# -----------------------------------------------------------------------------
# Event Parsers
# -----------------------------------------------------------------------------


def parse_events_list(soup: BeautifulSoup) -> list[tuple[str, str, Optional[datetime]]]:
    """
    Parse events listing page.

    Returns list of (event_id, event_name, event_date).
    """
    events = []
    table = soup.find("table", class_="b-statistics__table-events")
    if not table:
        return events

    rows = table.find_all("tr", class_="b-statistics__table-row")
    for row in rows:
        link = row.find("a", class_="b-link")
        if not link:
            continue

        href = link.get("href", "")
        if "/event-details/" not in href:
            continue

        event_id = _extract_id_from_url(href)
        event_name = _get_text(link)

        # Date is in a span with specific class
        date_span = row.find("span", class_="b-statistics__date")
        event_date = _parse_date(_get_text(date_span)) if date_span else None

        events.append((event_id, event_name, event_date))

    return events


def parse_upcoming_events(soup: BeautifulSoup) -> list[tuple[str, str, Optional[datetime], Optional[str]]]:
    """
    Parse upcoming events page.

    Returns list of (event_id, event_name, event_date, location).
    """
    events = []
    table = soup.find("table", class_="b-statistics__table-events")
    if not table:
        return events

    rows = table.find_all("tr", class_="b-statistics__table-row")
    for row in rows:
        link = row.find("a", class_="b-link")
        if not link:
            continue

        href = link.get("href", "")
        if "/event-details/" not in href:
            continue

        event_id = _extract_id_from_url(href)
        event_name = _get_text(link)

        # Date is in a span with specific class
        date_span = row.find("span", class_="b-statistics__date")
        event_date = _parse_date(_get_text(date_span)) if date_span else None

        # Location is in another column
        location = None
        cells = row.find_all("td")
        if len(cells) >= 2:
            location = _get_text(cells[1])
            if location == "--" or not location:
                location = None

        events.append((event_id, event_name, event_date, location))

    return events


def parse_event_details(soup: BeautifulSoup, event_id: str) -> Event:
    """Parse single event details page."""
    # Event name
    name_elem = soup.find("span", class_="b-content__title-highlight")
    name = _get_text(name_elem) if name_elem else "Unknown Event"

    # Date and location from list items
    event_date = None
    location = None
    info_items = soup.find_all("li", class_="b-list__box-list-item")
    for item in info_items:
        text = _get_text(item)
        if "Date:" in text:
            date_str = text.replace("Date:", "").strip()
            event_date = _parse_date(date_str)
        elif "Location:" in text:
            location = text.replace("Location:", "").strip()

    # Get fight IDs from the fight table
    fight_ids = []
    fight_table = soup.find("table", class_="b-fight-details__table")
    if fight_table:
        rows = fight_table.find_all("tr", class_="b-fight-details__table-row")
        for row in rows:
            # Skip header row
            if row.find("th"):
                continue
            # Get fight link
            link = row.get("data-link")
            if link and "/fight-details/" in link:
                fight_ids.append(_extract_id_from_url(link))

    return Event(
        event_id=event_id,
        name=name,
        event_date=event_date,
        location=location,
        fight_ids=fight_ids,
    )


# -----------------------------------------------------------------------------
# Fight Parsers
# -----------------------------------------------------------------------------


def parse_fight_details(soup: BeautifulSoup, fight_id: str, event_id: str) -> Fight:
    """Parse single fight details page."""
    # Get fighters
    fighter_links = soup.find_all("a", class_="b-link b-fight-details__person-link")
    fighter1_id = ""
    fighter2_id = ""
    if len(fighter_links) >= 2:
        fighter1_id = _extract_id_from_url(fighter_links[0].get("href", ""))
        fighter2_id = _extract_id_from_url(fighter_links[1].get("href", ""))

    # Winner determination - check for the "W" icon
    winner_id = None
    person_divs = soup.find_all("div", class_="b-fight-details__person")
    for i, div in enumerate(person_divs[:2]):
        status = div.find("i", class_="b-fight-details__person-status")
        if status and "W" in _get_text(status):
            winner_id = fighter1_id if i == 0 else fighter2_id
            break

    # Fight info section
    weight_class = None
    method = None
    method_detail = None
    round_finished = None
    time_finished = None
    is_title_fight = False
    scheduled_rounds = 3
    referee = None

    # Weight class from bout title (e.g., "Women's Bantamweight Bout")
    title_elem = soup.find("i", class_="b-fight-details__fight-title")
    if title_elem:
        title_text = _get_text(title_elem)
        weight_classes = [
            "Women's Strawweight",
            "Women's Flyweight",
            "Women's Bantamweight",
            "Women's Featherweight",
            "Strawweight",
            "Flyweight",
            "Bantamweight",
            "Featherweight",
            "Lightweight",
            "Welterweight",
            "Middleweight",
            "Light Heavyweight",
            "Heavyweight",
            "Catchweight",
        ]
        for wc in weight_classes:
            if wc.lower() in title_text.lower():
                weight_class = wc
                break
        if "title" in title_text.lower() or "championship" in title_text.lower():
            is_title_fight = True
            scheduled_rounds = 5

    # Parse fight details from the content section
    # Method is in: <i class="b-fight-details__text-item_first"> with label "Method:"
    content_section = soup.find("div", class_="b-fight-details__content")
    if content_section:
        # Find all text items
        text_items = content_section.find_all("i", class_=lambda x: x and "b-fight-details__text-item" in x)
        for item in text_items:
            label = item.find("i", class_="b-fight-details__label")
            if not label:
                continue
            label_text = _get_text(label)

            if "Method:" in label_text:
                # Method value is in a sibling <i> element with style="font-style: normal"
                method_elem = item.find("i", style=lambda x: x and "font-style" in x)
                if method_elem:
                    method_text = _get_text(method_elem)
                else:
                    # Fallback: get text after label
                    full_text = _get_text(item).replace("Method:", "").strip()
                    method_text = full_text

                # Parse method
                if "Decision" in method_text:
                    method = "Decision"
                    if "Unanimous" in method_text:
                        method_detail = "Unanimous"
                    elif "Split" in method_text:
                        method_detail = "Split"
                    elif "Majority" in method_text:
                        method_detail = "Majority"
                elif "KO/TKO" in method_text or "TKO" in method_text:
                    method = "KO/TKO"
                elif "KO" in method_text and "TKO" not in method_text:
                    method = "KO/TKO"
                elif "Submission" in method_text or "SUB" in method_text:
                    method = "Submission"
                elif "DQ" in method_text or "Disqualification" in method_text:
                    method = "DQ"
                elif "Overturned" in method_text or "NC" in method_text:
                    method = "NC"
                else:
                    method = method_text

            elif "Round:" in label_text:
                text = _get_text(item)
                round_match = re.search(r"Round:\s*(\d+)", text)
                if round_match:
                    round_finished = int(round_match.group(1))

            elif "Time:" in label_text:
                text = _get_text(item)
                time_match = re.search(r"Time:\s*([\d:]+)", text)
                if time_match:
                    time_finished = time_match.group(1)

            elif "Time format:" in label_text:
                text = _get_text(item)
                # Parse "5 Rnd (5-5-5-5-5)" to get scheduled rounds
                format_match = re.search(r"(\d+)\s*Rnd", text)
                if format_match:
                    scheduled_rounds = int(format_match.group(1))

            elif "Referee:" in label_text:
                # Referee name is in a span inside the item
                ref_span = item.find("span")
                if ref_span:
                    referee = _get_text(ref_span)
                else:
                    referee = _get_text(item).replace("Referee:", "").strip()

    # Parse detailed stats from totals table
    fighter1_stats = None
    fighter2_stats = None

    # Find the stats table (look for table with the right structure)
    tables = soup.find_all("table")
    for table in tables:
        tbody = table.find("tbody", class_="b-fight-details__table-body")
        if not tbody:
            continue

        rows = tbody.find_all("tr", class_="b-fight-details__table-row")
        for row in rows:
            cols = row.find_all("td", class_="b-fight-details__table-col")
            if len(cols) < 10:
                continue

            # Each column has <p class="b-fight-details__table-text"> for each fighter
            # Column order: Fighter, KD, Sig.Str., Sig.Str.%, Total Str., TD, TD%, Sub.Att, Rev., Ctrl

            f1_stats = FightStats(fighter_id=fighter1_id)
            f2_stats = FightStats(fighter_id=fighter2_id)

            def get_col_values(col_idx):
                """Get the two values (fighter1, fighter2) from a column."""
                if col_idx >= len(cols):
                    return "", ""
                col = cols[col_idx]
                texts = col.find_all("p", class_="b-fight-details__table-text")
                if len(texts) >= 2:
                    return _get_text(texts[0]), _get_text(texts[1])
                return "", ""

            # KD (knockdowns) - column 1
            v1, v2 = get_col_values(1)
            f1_stats.knockdowns = int(v1) if v1.isdigit() else 0
            f2_stats.knockdowns = int(v2) if v2.isdigit() else 0

            # Sig strikes - column 2 (format: "154 of 301")
            v1, v2 = get_col_values(2)
            l1, a1 = _parse_strike_stats(v1)
            l2, a2 = _parse_strike_stats(v2)
            f1_stats.sig_strikes_landed = l1
            f1_stats.sig_strikes_attempted = a1
            f2_stats.sig_strikes_landed = l2
            f2_stats.sig_strikes_attempted = a2

            # Total strikes - column 4 (format: "187 of 342")
            v1, v2 = get_col_values(4)
            l1, a1 = _parse_strike_stats(v1)
            l2, a2 = _parse_strike_stats(v2)
            f1_stats.total_strikes_landed = l1
            f1_stats.total_strikes_attempted = a1
            f2_stats.total_strikes_landed = l2
            f2_stats.total_strikes_attempted = a2

            # Takedowns - column 5 (format: "5 of 14")
            v1, v2 = get_col_values(5)
            l1, a1 = _parse_strike_stats(v1)
            l2, a2 = _parse_strike_stats(v2)
            f1_stats.takedowns_landed = l1
            f1_stats.takedowns_attempted = a1
            f2_stats.takedowns_landed = l2
            f2_stats.takedowns_attempted = a2

            # Submission attempts - column 7
            v1, v2 = get_col_values(7)
            f1_stats.sub_attempts = int(v1) if v1.isdigit() else 0
            f2_stats.sub_attempts = int(v2) if v2.isdigit() else 0

            # Reversals - column 8
            v1, v2 = get_col_values(8)
            f1_stats.reversals = int(v1) if v1.isdigit() else 0
            f2_stats.reversals = int(v2) if v2.isdigit() else 0

            # Control time - column 9 (format: "5:16")
            v1, v2 = get_col_values(9)
            f1_stats.control_time_seconds = _parse_control_time(v1)
            f2_stats.control_time_seconds = _parse_control_time(v2)

            fighter1_stats = f1_stats
            fighter2_stats = f2_stats
            break  # Only need first data row

        if fighter1_stats:
            break  # Found the stats table

    return Fight(
        fight_id=fight_id,
        event_id=event_id,
        fighter1_id=fighter1_id,
        fighter2_id=fighter2_id,
        winner_id=winner_id,
        weight_class=weight_class,
        is_title_fight=is_title_fight,
        method=method,
        method_detail=method_detail,
        round_finished=round_finished,
        time_finished=time_finished,
        scheduled_rounds=scheduled_rounds,
        referee=referee,
        fighter1_stats=fighter1_stats,
        fighter2_stats=fighter2_stats,
    )


# -----------------------------------------------------------------------------
# Fighter Parsers
# -----------------------------------------------------------------------------


def parse_fighters_list(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """
    Parse fighters listing page.

    Returns list of (fighter_id, fighter_name).
    """
    fighters = []
    table = soup.find("table", class_="b-statistics__table")
    if not table:
        return fighters

    rows = table.find_all("tr", class_="b-statistics__table-row")
    for row in rows:
        link = row.find("a", class_="b-link")
        if not link:
            continue

        href = link.get("href", "")
        if "/fighter-details/" not in href:
            continue

        fighter_id = _extract_id_from_url(href)
        # Get full name from the row
        name_cells = row.find_all("td")[:2]  # First and last name in separate cells
        name_parts = [_get_text(cell) for cell in name_cells]
        fighter_name = " ".join(name_parts).strip()

        fighters.append((fighter_id, fighter_name))

    return fighters


def parse_fighter_details(soup: BeautifulSoup, fighter_id: str) -> Fighter:
    """Parse single fighter details page."""
    # Name
    name_elem = soup.find("span", class_="b-content__title-highlight")
    name = _get_text(name_elem) if name_elem else "Unknown"

    # Nickname
    nickname_elem = soup.find("p", class_="b-content__Nickname")
    nickname = _get_text(nickname_elem) if nickname_elem else None
    if nickname:
        nickname = nickname.strip('"')

    # Record
    record_elem = soup.find("span", class_="b-content__title-record")
    record_str = _get_text(record_elem) if record_elem else ""
    record_str = record_str.replace("Record:", "").strip()
    wins, losses, draws, nc = _parse_record(record_str)

    # Physical stats and career stats from the info box
    height = None
    weight = None
    reach = None
    stance = None
    dob = None
    slpm = None
    str_acc = None
    sapm = None
    str_def = None
    td_avg = None
    td_acc = None
    td_def = None
    sub_avg = None

    # Bio info box
    info_items = soup.find_all("li", class_="b-list__box-list-item")
    for item in info_items:
        text = _get_text(item)
        if "Height:" in text:
            height = _parse_height(text.replace("Height:", ""))
        elif "Weight:" in text:
            weight = _parse_weight(text.replace("Weight:", ""))
        elif "Reach:" in text:
            reach = _parse_reach(text.replace("Reach:", ""))
        elif "STANCE:" in text.upper():
            stance = text.upper().replace("STANCE:", "").strip()
            if stance and stance != "--":
                stance = stance.title()
            else:
                stance = None
        elif "DOB:" in text.upper():
            dob = _parse_date(text.upper().replace("DOB:", ""))

    # Career stats box
    career_items = soup.find_all("li", class_="b-list__box-list-item_type_block")
    for item in career_items:
        text = _get_text(item)
        if "SLpM:" in text:
            slpm = _parse_float(text.replace("SLpM:", ""))
        elif "Str. Acc.:" in text:
            str_acc = _parse_percentage(text.replace("Str. Acc.:", ""))
        elif "SApM:" in text:
            sapm = _parse_float(text.replace("SApM:", ""))
        elif "Str. Def:" in text or "Str. Def.:" in text:
            str_def = _parse_percentage(text.replace("Str. Def:", "").replace("Str. Def.:", ""))
        elif "TD Avg.:" in text:
            td_avg = _parse_float(text.replace("TD Avg.:", ""))
        elif "TD Acc.:" in text:
            td_acc = _parse_percentage(text.replace("TD Acc.:", ""))
        elif "TD Def.:" in text:
            td_def = _parse_percentage(text.replace("TD Def.:", ""))
        elif "Sub. Avg.:" in text:
            sub_avg = _parse_float(text.replace("Sub. Avg.:", ""))

    return Fighter(
        fighter_id=fighter_id,
        name=name,
        nickname=nickname,
        height_inches=height,
        weight_lbs=weight,
        reach_inches=reach,
        stance=stance,
        dob=dob,
        record_wins=wins,
        record_losses=losses,
        record_draws=draws,
        record_nc=nc,
        slpm=slpm,
        str_acc=str_acc,
        sapm=sapm,
        str_def=str_def,
        td_avg=td_avg,
        td_acc=td_acc,
        td_def=td_def,
        sub_avg=sub_avg,
    )
