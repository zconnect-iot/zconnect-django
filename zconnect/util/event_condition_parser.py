import datetime
import logging

from pyparsing import Combine, Word, alphas, nums, oneOf, opAssoc, operatorPrecedence

logger = logging.getLogger(__name__)

class Condition:
    """ A condition object which parses condition strings and can evaluate them against variables.
    """
    def __init__(self, condition_string):
        """

        Args:
            condition_string: The condition string to parse.

        Returns:

        """
        self.condition_string = condition_string.lower()
        if self.condition_string:
            self.parser = ConditionParser(self.condition_string)


    def evaluate(self, context, last_eval_time):
        """

        Args:
            context: The context to parse the condition with. This should be a dictionary with keys matching
                     variable names in the condition

        Returns: Boolean, whether the condition evaluates to True or False

        """
        if not hasattr(self, 'parser'):
            return False

        return self.parser.parse(context, last_eval_time)


class ConditionParser:
    def __init__(self, expression):
        # define the parser
        integer = Word(nums)
        real = Combine(Word(nums) + "." + Word(nums))
        # nums have been added to allow for aggregation variables such as `sum_250_field`
        variable = Word(alphas + ":" + "_" + nums)
        boolean = oneOf('true false', caseless=True)
        num = integer | real
        keyword = oneOf('time day period')

        boolean.setParseAction(EvalBool)
        variable.setParseAction(EvalVar)
        num.setParseAction(EvalNum)
        keyword.setParseAction(EvalKeyword)

        bool_op = oneOf('&& ||')
        sign_op = oneOf('+ -')
        comparison_op = oneOf("< <= > >= != ==")

        atom = boolean | keyword | num | variable | bool_op | sign_op | comparison_op

        self.expr = operatorPrecedence(atom,
                                  [
                                      (sign_op, 1, opAssoc.RIGHT, EvalSignOp),
                                      (comparison_op, 2, opAssoc.LEFT, EvalComparisonOp),
                                      (bool_op, 2, opAssoc.LEFT, EvalLogical)
                                  ])
        self.parsed = self.expr.parseString(expression)[0]

    def parse(self, context, last_eval_time):
        return self.parsed.eval(context, last_eval_time)

def getByColonNotation(obj, ref):
    val = obj
    for key in ref.split( ':' ):
        val = val[key]
    return val


class EvalNum():
    def __init__(self, tokens):
        self.value = tokens[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument
        return float(self.value)


class EvalBool():
    def __init__(self, tokens):
        self.value = tokens[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument
        return self.value == 'True' or self.value == 'true'


class EvalVar():
    def __init__(self, tokens):
        self.value = tokens[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument
        try:
            return getByColonNotation(context, self.value)
        except (AttributeError, KeyError):
            pass


class EvalSignOp:
    """ Class to evaluate expressions with a leading + or - sign
    """
    def __init__(self, tokens):
        self.sign, self.value = tokens[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument
        mult = {'+':1, '-':-1}[self.sign]
        return mult * self.value.eval(context, last_eval_time)


def operatorOperands(tokenlist):
    """ Generator to extract operators and operands in pairs
    """
    it = iter(tokenlist)
    while 1:
        try:
            yield (next(it), next(it))
        except StopIteration:
            break

class EvalComparisonOp:
    """ Evaluate comparison expressions
    """
    opMap = {
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "!=": lambda a, b: a != b,
        "==": lambda a, b: a == b,
    }

    def __init__(self, tokens):
        self.value = tokens[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument

        # Ignore any terms with a keyword since these will be evaluated elsewhere
        if isinstance(self.value[0], EvalKeyword):
            return evalKeyword(self.value, last_eval_time)
        val1 = self.value[0].eval(context, last_eval_time)
        try:
            for op,val in operatorOperands(self.value[1:]):
                fn = EvalComparisonOp.opMap[op]
                val2 = val.eval(context, last_eval_time)
                if not fn(val1, val2):
                    break
                val1 = val2
            else:
                return True
            return False
        except (KeyError, TypeError):
            return False


class EvalLogical:
    """ Evaluate logical operators. AND and NOT
    """
    opMap = {
        "&&": lambda a, b: a and b,
        "||": lambda a, b: a or b,
    }

    def __init__(self, tokens):
        self.value = tokens[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument
        val1 = self.value[0].eval(context, last_eval_time)
        for op, val in operatorOperands(self.value[1:]):
            fn = EvalLogical.opMap[op]
            val2 = val.eval(context, last_eval_time)
            if not fn(val1, val2):
                break
            val1 = val2
        else:
            return True
        return False

def evalKeyword(value, last_eval_time):
    """
    Evaluate a keyword expression.

    Assumes that operator is always ==

    Args:
        value: The parsed Expression. Should contain [EvalKeyword, Operator, EvalNum]
        last_eval_time: The last time this condition was evaluated

    Returns:

    """
    # Here we would connect to redis and check the last eval time.
    keyword = value[0].value
    comparison = value[2].value
    dispatch_table = {
        'time': evaluate_time,
        'day': evaluate_day,
        'period': evaluate_period,
    }
    try:
        return dispatch_table[keyword](comparison, last_eval_time)
    except KeyError:
        # TODO: What to do here? This is pretty unrecoverable
        logger.warning("Could not find keyword in dispatch Table")
        return False


def evaluate_time(comparison, last_eval_time):
    now = datetime.datetime.utcnow()
    comparison_ts = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(seconds=float(comparison))
    last = datetime.datetime.utcfromtimestamp(last_eval_time)
    logger.debug("Checking times: %s < %s <= %s", last, comparison_ts, now)
    result = last < comparison_ts <= now
    return result

def evaluate_day(comparison, last_eval_time):
    # pylint: disable=unused-argument
    # If last evaluation was on a day not equal to the comparison then do it.
    # Get the day of the last eval.
    comparison = int(comparison)
    now = datetime.datetime.utcnow()

    logger.debug("Checking days: %s == %s", now.weekday(), comparison)
    result = (now.weekday() == comparison)
    return result


def evaluate_period(comparison, last_eval_time):
    # Comparison == hourly, daily, weekly, monthly, yearly
    # If the last eval was
    now = datetime.datetime.utcnow()
    last = datetime.datetime.utcfromtimestamp(last_eval_time)

    period_seconds = {
        'minutely': datetime.timedelta(minutes=1),
        'hourly': datetime.timedelta(hours=1),
        'daily': datetime.timedelta(days=1),
        'weekly': datetime.timedelta(weeks=1),
        'monthly': datetime.timedelta(weeks=4),
        'yearly': datetime.timedelta(weeks=52),
    }
    logger.debug("Comparing period: %s, period_seconds: %s, now: %s, last: %s", comparison, period_seconds, now, last)
    return now - last > period_seconds[comparison]

class EvalKeyword:
    def __init__(self, token):
        self.value = token[0]

    def eval(self, context, last_eval_time):
        # pylint: disable=unused-argument
        return True
