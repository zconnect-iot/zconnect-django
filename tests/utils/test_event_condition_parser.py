import datetime

from freezegun import freeze_time
import pytest

from zconnect.util.event_condition_parser import Condition

freezer_ts = 1400000000
freezer_time = datetime.datetime.utcfromtimestamp(freezer_ts)
freezer_string = freezer_time.isoformat()

long_before = freezer_ts - 100000
before = freezer_ts - 1000
after = freezer_ts + 1000

seconds_before = freezer_ts - 30 # 30 seconds before
mins_before = freezer_ts - 120 # 2 mins before
hours_before = freezer_ts - 7200 # 2 hours before
days_before = freezer_ts - 172800 # 2 days before
weeks_before = freezer_ts - 1209600 # 2 weeks before
months_before = freezer_ts - 5184000 # 60 days before
years_before = freezer_ts - 51840000 # 600 days before

def time_since_midnight(input):
    return (input - input.replace(hour=0, minute=0, second=0, microsecond=0))

# Conditions needed for test cases
conditions = [
    Condition("temp==10"), #0
    Condition("temp>=10"), #1
    Condition("temp<25"), #2
    Condition("temp<25 && temp>=10"), #3
    Condition("(temp != 10) && (temp<=25)"), #4
    Condition("(temp<10) || (temp>25)"), #5
    Condition("hum>70"), #6
    Condition("pir:motion==true"), #7
    Condition("day==1"), #8
    Condition("day==1 && time==300"), #9
    Condition("time=={}".format(time_since_midnight(freezer_time).total_seconds())), # 10
    Condition("nested_state:away==true"), #11
    Condition("period==minutely"), # 12
    Condition("period==hourly"), # 13
    Condition("period==daily"), # 14
    Condition("period==weekly"), # 15
    Condition("period==monthly"), # 16
    Condition("period==yearly"), # 17
    Condition("pir:motion==true && temp>=10"), #18
    Condition("nested_state:schedule_on==true&&nested_state:away==false"), #19
    Condition("non_existant:field==true"), #20
    Condition("fvalue==false"), #21
    Condition("") #22
]

@pytest.mark.parametrize("condition, context, expected", [
    (conditions[0], {"temp": 10}, True),
    (conditions[0], {"temp": -10}, False),
    (conditions[0], {"temp": 20}, False),
    (conditions[1], {"temp": 30}, True),
    (conditions[1], {"temp": 9}, False),
    (conditions[1], {"temp": 10}, True),
    (conditions[2], {"temp": 30}, False),
    (conditions[2], {"temp": 25}, False),
    (conditions[2], {"temp": 9}, True),
    (conditions[3], {"temp": 30}, False),
    (conditions[3], {"temp": 15}, True),
    (conditions[3], {"temp": 9}, False),
    (conditions[4], {"temp": 10}, False),
    (conditions[4], {"temp": 11}, True),
    (conditions[4], {"temp": 26}, False),
    (conditions[5], {"temp": 26}, True),
    (conditions[5], {"temp": 9}, True),
    (conditions[5], {"temp": 10}, False),
    (conditions[5], {"temp": 25}, False),
    (conditions[6], {"hum": 60}, False),
    (conditions[6], {"hum": 75, "temp": 12}, True),
    (conditions[7], {"pir": {"motion": True}}, True),
    (conditions[7], {"pir": {"motion": False}}, False),
    (conditions[18], {"pir": {"motion": True}, "temp": 25}, True),
    (conditions[18], {"pir": {"motion": True}, "temp": 5}, False),
    (conditions[18], {"pir": {"motion": False}, "temp": 25}, False),
    (conditions[19], {"nested_state": {"schedule_on": True, "away": False}}, True),
    (conditions[19], {"nested_state": {"schedule_on": False, "away": False}}, False),
    (conditions[19], {"nested_state": {"schedule_on": True, "away": True}}, False),
    (conditions[20], {}, False),
    (conditions[21], {"fvalue": False}, True),
    (conditions[22], {}, False)
])
def test_condition_parser(condition, context, expected):
    assert condition.evaluate(context=context, last_eval_time=100) == expected

@pytest.mark.parametrize("test_name, condition, last_eval_time, context, expected", [
    ("1", conditions[8], 100, {"day": 0}, True), # Monday
    ("2", conditions[8], 100, {"day": 0}, True), # Monday
    ("3", conditions[0], 100, {"day": 0}, False), # Monday
    ("4", conditions[8], 100, {"day": 0, "temp": 100}, True), # Monday
    ("5", conditions[8], long_before, {"temp": 100}, True), # Monday
    ("6", conditions[9], long_before, {"temp": 100}, True), # Monday
    ("7", conditions[10], long_before, {"temp": 100}, True), # Monday
    ("8", conditions[11], 100, {"nested_state": {"away": True}}, True),
    ("9", conditions[11], 100, {"nested_state": {"away": False}}, False),
    ("10", conditions[10], freezer_ts, {}, False), # Last evaluated now - shouldn't test again
    ("11", conditions[10], after, {}, False), # Last evaluated in the future
    ("12", conditions[10], before, {}, True),
    ("13", conditions[12], seconds_before, {}, False),
    ("14", conditions[12], mins_before, {}, True),
    ("15", conditions[13], mins_before, {}, False),
    ("16", conditions[13], hours_before, {}, True),
    ("17", conditions[14], hours_before, {}, False),
    ("18", conditions[14], days_before, {}, True),
    ("19", conditions[15], days_before, {}, False),
    ("20", conditions[15], weeks_before, {}, True),
    ("21", conditions[16], weeks_before, {}, False),
    ("22", conditions[16], months_before, {}, True),
    ("23", conditions[17], months_before, {}, False),
    ("24", conditions[17], years_before, {}, True),
])

@freeze_time(freezer_string)
def test_condition_day_parser(test_name, condition, last_eval_time, context, expected):
    print("Test: {}".format(test_name))
    assert condition.evaluate(context=context, last_eval_time=last_eval_time) == expected
