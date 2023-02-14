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


class CloudWatchVPN:
    """
    Encapsulates Amazon CloudWatch VPN functions.
    """

    def __init__(self, vpn, cloudwatchclient, default_values):
        ciname = ""
        cloudid = vpn["VpnConnectionId"]

        name_result = list(
                filter(lambda tag: tag["Key"] == "Name", vpn["Tags"]))
        if len(name_result) > 0:
            ciname = name_result[0]["Value"]

        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchVPN, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    vpn, ciname, cloudid, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=cloudid,
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchVPN,
                                            vpn,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "VpnId",
                                                "Value": cloudid
                                            }],
                                            cloudwatchclient
                                            )
