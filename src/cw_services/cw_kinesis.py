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

from src.utility import Utility

LOGGER = logging.getLogger()


class CloudWatchKinesis:
    """
    Encapsulates Amazon CloudWatch Kinesis functions.
    """

    def __init__(self, kinesis, cloudwatchclient, default_values):
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            cloudid = kinesis["StreamArn"]
            ciname = kinesis["StreamName"]

            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchKinesis, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    kinesis, ciname, cloudid, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=kinesis["AcceleratorArn"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchKinesis,
                                            kinesis,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "StreamArn",
                                                "Value": kinesis["StreamArn"]
                                            }],
                                            cloudwatchclient
                                            )
