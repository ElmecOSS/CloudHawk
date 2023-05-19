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
import math

from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchEFS:
    """
    Encapsulates Amazon CloudWatch EFS functions.
    """

    @staticmethod
    def burst_credit_balance_threshold_dynamic(efs, alarm_values):
        """
        Dynamic Threshold calculation for BurstCreditBalance metrics
        :return: Threshold value to be used
        """
        # exp is the exponent that you have to assign to efs' size in byte, to get a specific dimension. 0 => Byte, 1 = KB, 2 => MB, 3 => GB, 4 => TB
        # https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python
        exp = int(math.floor(math.log(efs["SizeInBytes"]["Value"], 1024)))
        actual_tb = 1
        if exp > 3:
            p = math.pow(1024, exp)
            actual_tb = int(efs["SizeInBytes"]["Value"] / p)

        return (actual_tb*2.31*pow(10, 12))*(float(alarm_values["MetricSpecifications"]["Threshold"])/100)

    @staticmethod
    def burst_credit_balance_creation_dynamic(efs, alarm_values):
        """
        Creation condition for BustCreditBalance metrics
        :return: if the metrics needs to be created or not
        """
        return efs["ThroughputMode"] == "bursting"

    def __init__(self, efs, cloudwatchclient, default_values):
        # Extract valid metrics for resource type and engine
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            ciname = efs["Name"]
            cloudid = efs["FileSystemId"]

            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchEFS, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    efs, ciname, cloudid, cloudwatchclient, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=efs["FileSystemId"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchEFS,
                                            efs,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "FileSystemId",
                                                "Value": efs["FileSystemId"]
                                            }],
                                            cloudwatchclient
                                            )
