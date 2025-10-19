import logging

# Define custom logging levels
ACTIVITY_LEVEL_NUM = 25
ALERT_LEVEL_NUM = 35
BREACH_LEVEL_NUM = 45

logging.addLevelName(ACTIVITY_LEVEL_NUM, "ACTIVITY")
logging.addLevelName(ALERT_LEVEL_NUM, "ALERT")
logging.addLevelName(BREACH_LEVEL_NUM, "BREACH")

# Add methods to Logger for custom levels
def activity(self, message, *args, **kws):
    if self.isEnabledFor(ACTIVITY_LEVEL_NUM):
        self._log(ACTIVITY_LEVEL_NUM, message, args, **kws, stacklevel=2)

def alert(self, message, *args, **kws):
    if self.isEnabledFor(ALERT_LEVEL_NUM):
        self._log(ALERT_LEVEL_NUM, message, args, **kws, stacklevel=2)

def breach(self, message, *args, **kws):
    if self.isEnabledFor(BREACH_LEVEL_NUM):
        self._log(BREACH_LEVEL_NUM, message, args, **kws, stacklevel=2)

logging.Logger.activity = activity
logging.Logger.alert = alert
logging.Logger.breach = breach
