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


class CloudWatchOS:
    """
    Encapsulates Amazon CloudWatch OpenSearch functions.
    """

    @staticmethod
    def free_storage_space_threshold_dynamic(os, alarm_values):
        """
        Dynamic Threshold calculation for FreeStorageSpace metrics
        :return: Threshold value to be used
        """
        # ["EBSOptions"]["VolumeSize"] GiB. 25% O.S. Reserved.
        # https://docs.aws.amazon.com/opensearch-service/latest/developerguide/sizing-domains.html
        disk_size = 1073741824 * \
            ((os["EBSOptions"]["VolumeSize"]*75/100)/1000000)
        # Threshold in MB
        # 10 GiB = 10.737,4 megabytes
        return disk_size*(float(alarm_values["MetricSpecifications"]["Threshold"])/100)

    def __init__(self, os, cloudwatchclient, default_values):
        ciname = os["DomainName"]
        cloudid = os["ARN"]

        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Invoke the creation method for extracted metrics
        for metric_name in metric_needed:
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchOS, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    os, ciname, cloudid, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=os["DomainName"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchOS,
                                            os,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "DomainName",
                                                "Value": os["DomainName"]
                                            },
                    {
                                                "Name": "ClientId",
                                                "Value": os["DomainId"].split("/")[0]
                                            }],
                                            cloudwatchclient
                                            )
