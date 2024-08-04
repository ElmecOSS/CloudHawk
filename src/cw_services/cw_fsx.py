# ______________________________________________________
#  Author: Cominoli Luca, Dalle Fratte Andrea
#  GitHub Source Code: https://github.com/ElmecOSS/CloudHawk
#  License: GNU GPLv3
#  Copyright (C) 2022  Elmec Informatica S.p.A.

#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ______________________________________________________

import logging

from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchFSx:
    """
    Encapsulates Amazon CloudWatch FSx functions.
    """

    def __init__(self, fsx, cloudwatchclient, default_values):
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            cloudid = fsx["FileSystemId"]
            name_result = list(filter(lambda tag: tag["Key"] == "Name", fsx["Tags"]))
            if len(name_result) == 0:
                raise Exception("Cannot find the name for the FSx")
            ciname = name_result[0]["Value"]

            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchFSx, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    fsx, ciname, cloudid, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=fsx["FileSystemId"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchFSx,
                                            fsx,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "FileSystemId",
                                                "Value": fsx["FileSystemId"]
                                            }],
                                            cloudwatchclient
                                            )
