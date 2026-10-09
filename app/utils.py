import datetime

def format_dmy(value, include_time=True):
    """
    Format a date, datetime, or ISO date string into day/month/year format:
    DD/MM/YYYY or DD/MM/YYYY HH:MM:SS.
    """
    if value is None or value == '':
        return ''

    if isinstance(value, datetime.datetime):
        if include_time:
            return value.strftime('%d/%m/%Y %H:%M:%S')
        return value.strftime('%d/%m/%Y')

    if isinstance(value, datetime.date):
        return value.strftime('%d/%m/%Y')

    s = str(value).strip()
    # Handle ISO formatted strings (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        parts = s.split(' ', 1)
        date_parts = parts[0].split('-')
        if len(date_parts) == 3:
            y, m, d = date_parts
            formatted_date = f"{d}/{m}/{y}"
            if len(parts) == 2 and include_time:
                return f"{formatted_date} {parts[1]}"
            return formatted_date

    return s

def format_date_dmy(value):
    """
    Format a date, datetime, or ISO string into day/month/year (DD/MM/YYYY)
    without the time component.
    """
    return format_dmy(value, include_time=False)
