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


class CloudWatchElastiCache:
    """
    Encapsulates Amazon CloudWatch ElastiCache functions.
    """

    def __init__(self, elasticache, cloudwatchclient, default_values):
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            cloudid = elasticache["ClusterInfo"][0]["CacheClusterId"]
            ciname = elasticache["ClusterInfo"][0]["ReplicationGroupId"]

            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchElastiCache, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    elasticache, ciname, cloudid, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=elasticache["ClusterInfo"][0]["CacheClusterId"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchElastiCache,
                                            elasticache,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "CacheClusterId",
                                                "Value": elasticache["ClusterInfo"][0]["CacheClusterId"]
                                            }],
                                            cloudwatchclient
                                            )
