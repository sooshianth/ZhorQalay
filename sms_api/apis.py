from sms_ir import SmsIr
from .models import SmsLog


api_key='mbdRODVCB2JHUX5c3IpetXsiDXFIT6bo7JZo0PhiTFWkuIN4'
linenumber=30000000


sms_account = SmsIr(api_key, linenumber)
def send_instant_sms(number:str, message:str, sms_account=sms_account):
    sms_account.send_sms(number, message, sms_account.linenumber,)
    SmsLog(
        reciepent_number=number,
        message=message
    )

def todays_sms_report(sms_account=sms_account):
    sms_account.report_today(
        page_size=20,
        page_number=15,
        )
    

