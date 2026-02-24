import calendar
from datetime import timedelta

def build_symbol(index, expiry_date, strike, option_type):

    index = index.upper()
    option_type = option_type.upper()

    year = str(expiry_date.year)[-2:]
    month_num = expiry_date.month
    day = expiry_date.day

    month_name = calendar.month_abbr[month_num].upper()

    next_week = expiry_date + timedelta(days=7)
    is_monthly = next_week.month != expiry_date.month
    is_monthly_true =     f"{index}{year}{month_num}{day:02d}{strike}{option_type}" 

    is_monthly_false =       f"{index}{year}{month_name}{strike}{option_type}" 

    if is_monthly:
        return is_monthly_true
    else:
        return is_monthly_false