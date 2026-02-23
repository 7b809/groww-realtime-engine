import calendar
from datetime import timedelta


def build_symbol(index, expiry_date, strike, option_type):
    """
    Builds Groww symbol format for:
    - Weekly expiry  → NIFTY2630225700CE
    - Monthly expiry → NIFTY26FEB25700CE
    """

    index = index.upper()
    option_type = option_type.upper()

    year = str(expiry_date.year)[-2:]   # Last 2 digits of year
    month_num = expiry_date.month
    day = expiry_date.day

    # Month name for monthly expiry
    month_name = calendar.month_abbr[month_num].upper()

    # Check if monthly expiry (last expiry of month)
    next_week = expiry_date + timedelta(days=7)
    is_monthly = next_week.month != expiry_date.month

    if is_monthly:
        # ✅ Monthly format
        # Example: NIFTY26FEB25700CE
        return f"{index}{year}{month_name}{strike}{option_type}"

    else:
        # ✅ Weekly format
        # Example: NIFTY2630225700CE
        month_part = str(month_num)         # No zero padding
        day_part = f"{day:02d}"             # Always 2-digit day

        return f"{index}{year}{month_part}{day_part}{strike}{option_type}"