"""Date of birth and sex collected at sign-up. It is private: stored on the account, never returned by any API.
Only the age band can be used for matching, and under-18 / 18+ accounts are separated by rule."""
import datetime,re
MIN_AGE=13
BANDS=((13,17,'13-17'),(18,24,'18-24'),(25,34,'25-34'),(35,44,'35-44'),(45,200,'45+'))
def parse(value,today=None):
    today=today or datetime.date.today()
    text=str(value or '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):raise ValueError('Enter your date of birth')
    try:born=datetime.date.fromisoformat(text)
    except ValueError:raise ValueError('Enter a valid date of birth') from None
    age=age_on(born,today)
    if born>today or age>120:raise ValueError('Enter a valid date of birth')
    if age<MIN_AGE:raise ValueError('You must be at least %d to use X ORBIT'%MIN_AGE)
    return text
def age_on(born,today=None):
    today=today or datetime.date.today()
    return today.year-born.year-((today.month,today.day)<(born.month,born.day))
def age_of(text,today=None):
    try:return age_on(datetime.date.fromisoformat(text),today) if text else None
    except ValueError:return None
def band(age):
    return next((label for low,high,label in BANDS if age is not None and low<=age<=high),None)
def is_adult(age):return age is not None and age>=18
SEXES=('male','female','undisclosed')
def parse_sex(value):
    text=str(value or '').strip().lower()
    if text not in SEXES:raise ValueError('Choose male, female or prefer not to say')
    return text
