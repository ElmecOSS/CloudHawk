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


class CloudWatchEBS:
    """
    Encapsulates Amazon CloudWatch EBS functions.
    """

    @staticmethod
    def __extract_attached_instance_id(attachments):
        for attachment in attachments:
            if attachment["State"] == "attached":
                return attachment["InstanceId"]
        return None

    @staticmethod
    def burstbalance_creation_dynamic(volume, default_values):
        """
        Creation condition for BurstBalance metrics
        :return: if the metrics needs to be created or not
        """
        return volume["VolumeType"] in default_values["MetricSpecifications"]["Types"]

    def __init__(self, volume, cloudwatchclient, default_values):
        attached_instance_id = CloudWatchEBS.__extract_attached_instance_id(
            volume["Attachments"])

        # Extract valid metrics for resource type and engine
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            ciname = volume["EC2Name"]
            cloudid = attached_instance_id
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchEBS, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    volume, ciname, cloudwatchclient, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=cloudid,
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchEBS,
                                            volume,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "VolumeId",
                                                "Value": volume["VolumeId"]
                                            }],
                                            cloudwatchclient
                                            )
