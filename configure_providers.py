"""Configure API access for this launch only. No keys are written to disk."""
import getpass
import os
import re
import warnings

from providers import PROVIDERS


def configure_session():
    choices = list(PROVIDERS.items())
    print("Provider setup for this session. Your API keys stay in this process.")
    print("Choose a provider, enter model IDs available to your account, then enter its API key.")
    while True:
        for idx, (_, (label, _, _)) in enumerate(choices, 1):
            print(f"  {idx}. {label}")
        selection = input("Provider number, or Enter to start Office Studio: ").strip()
        if not selection:
            return
        if selection not in {str(n) for n in range(1, len(choices) + 1)}:
            print("Choose a number from the list.")
            continue
        _, (label, key_var, model_var) = choices[int(selection) - 1]
        raw = input(f"{label} model IDs, default first, separated by commas: ")
        models = list(dict.fromkeys(s.strip() for s in raw.split(",")))
        if len(models) > 64 or not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", s) for s in models):
            print("Enter a model ID, such as the one shown in your provider dashboard.")
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                key = getpass.getpass(f"{label} API key (hidden; Enter skips): ").strip()
        except getpass.GetPassWarning as error:
            raise ValueError("A terminal with hidden input is required.") from error
        if not key:
            continue
        os.environ[key_var] = key
        os.environ[model_var] = models[0]
        os.environ[model_var + "S"] = ",".join(models[1:])
        print(f"{label} configured for this session. Its first live draft will check access.")
