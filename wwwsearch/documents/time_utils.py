# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import dateutil.parser
import pytz, iso8601 #support localising the timezone

def make_datefilter(start_date,end_date):
    assert isinstance(start_date,datetime) or not start_date
    assert isinstance(end_date,datetime) or not end_date
    if not start_date and not end_date:
        return None
    start_stamp=timestringGMT(start_date) if start_date else '*'
    end_stamp=timestringGMT(end_date+timedelta(days=1)) if end_date else '*'
    return "[{} TO {}]".format(start_stamp,end_stamp)
    
def timestamp2aware(timestamp):
    return timeaware(timefromstamp(timestamp))

def timefromstamp(timestamp):
    return datetime.fromtimestamp(timestamp)

def timeaware(dumbtimeobject):
    return pytz.timezone("GMT").localize(dumbtimeobject)
#Mac / Linux stores all file times etc in GMT, so localise to GMT

def timestring(timeobject):
    return "{:%B %d,%Y %I:%M%p}".format(timeobject)
    
def timestringGMT(timeobject):
    return timeobject.strftime("%Y-%m-%dT%H:%M:%SZ")
    
def ISOtimestring(timeobject_aware):
    return timeobject_aware.astimezone(pytz.utc).isoformat()[:19]+'Z'

def easydate(timeobject):
    return timeobject.strftime("%b %d, %Y")

def parseISO(timestring):
    return iso8601.parse_date(timestring)
    
def cleaned_ISOtimestring(rawstring):
    try:
        return ISOtimestring(parseISO(rawstring))
    except iso8601.ParseError as e:
        return None

def parse_time(time_string):
    return dateutil.parser.parse(time_string)


def iso_parse(time_string):
    return ISOtimestring(parse_time(time_string))