from .browser import BrowserAdapter
from .computer import ComputerAdapter
from .android import AndroidAdapter
from .ios import IOSAdapter
from .harmony import HarmonyAdapter
from .vitest_e2e import VitestE2EAdapter
def default_registry(): return {"browser":BrowserAdapter(), "computer":ComputerAdapter(), "android":AndroidAdapter(), "ios":IOSAdapter(), "harmony":HarmonyAdapter(), "vitest_e2e":VitestE2EAdapter()}
