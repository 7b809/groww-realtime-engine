import datetime

def get_next_expiries(index):
    today = datetime.date.today()

    if index in ["NIFTY", "BANKNIFTY"]:
        target_weekday = 1  # Tuesday (Mon=0)
    elif index == "SENSEX":
        target_weekday = 3  # Thursday
    else:
        return []

    expiries = []
    d = today

    while len(expiries) < 5:
        if d.weekday() == target_weekday:
            expiries.append(d)
        d += datetime.timedelta(days=1)

    return expiries