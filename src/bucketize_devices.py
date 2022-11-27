import argparse
import pandas as pd
from pathlib import Path
from collections import defaultdict
from natsort import natsorted

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Bucketizes all devices by their frame addresses.")
  parser.add_argument("fars_dir", type=str, help="Directory which contains 'fars.csv' file for every device.")
  args = parser.parse_args()

  deviceIdcode_fars_dict = dict[str, str]()

  fars_dir = Path(args.fars_dir)
  for p_fars in fars_dir.rglob("fars.csv"):
    device = p_fars.parent.name
    # print(device)

    df = pd.read_csv(p_fars)

    # For each IDCODE, we extract all FARs and concatenate them into a single string.
    for (idcode, group) in df.groupby("IDCODE"):
      fars = ",".join(group["FAR"])
      deviceIdcode_fars_dict[(device, idcode)] = fars

  # Now we bucketize all IDCODEs by the fars they contain.
  fars_deviceIdcode_dict: dict[str, list[str]] = defaultdict(list)
  for (deviceIdcode, fars) in deviceIdcode_fars_dict.items():
    fars_deviceIdcode_dict[fars].append(deviceIdcode)

  for (fars, deviceIdcode_list) in fars_deviceIdcode_dict.items():
    print(natsorted(deviceIdcode_list))

