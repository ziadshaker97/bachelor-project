import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_APPDATA = Path(os.getenv("LOCALAPPDATA", str(BASE_DIR)))
TEST_RUNTIME = LOCAL_APPDATA / "employee-onboarding-intelligence-tests" / "runtime"
TEST_TEMP = LOCAL_APPDATA / "employee-onboarding-intelligence-tests" / "temp"

TEST_RUNTIME.mkdir(parents=True, exist_ok=True)
TEST_TEMP.mkdir(parents=True, exist_ok=True)

os.environ["EOI_RUNTIME_DIR"] = str(TEST_RUNTIME)
os.environ["TEMP"] = str(TEST_TEMP)
os.environ["TMP"] = str(TEST_TEMP)
