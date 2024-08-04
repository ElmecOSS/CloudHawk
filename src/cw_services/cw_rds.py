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
import os
import re

import boto3

from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchRDS:
    """
    Encapsulates Amazon CloudWatch RDS functions.
    """

    @staticmethod
    def aurorareplicalag_creation_dynamic(database, alarm_values):
        """
        Creation condition for AuroraReplicaLag metrics
        :return: if the metrics needs to be created or not
        """
        # Metric available only in case of Replica
        return database.get("ReplicationSourceIdentifier", "") != ""

    @staticmethod
    def replicalag_creation_dynamic(database, alarm_values):
        """
        Creation condition for ReplicaLag metrics
        :return: if the metrics needs to be created or not
        """
        # Metric available only in case of Replica
        return database.get("ReadReplicaSourceDBInstanceIdentifier", "") != ""

    @staticmethod
    def freestoragespace_threshold_dynamic(database, alarm_values):
        """
        Dynamic Threshold calculation for FreeStorageSpace metrics
        :return: Threshold value to be used
        """
        # Specifies the allocated storage size specified in gibibytes (GiB).
        # ["AllocatedStorage"] in GiB.
        # https://docs.aws.amazon.com/opensearch-service/latest/developerguide/sizing-domains.html

        # Check if it's present the autoscaling feature for storage
        disk_size = 1073741824 * ((database["AllocatedStorage"]))
        # Threshold in MB
        # 10 GiB = 10.737,4 megabytes
        return disk_size * (alarm_values["MetricSpecifications"]["Threshold"] / 100)

    @staticmethod
    def burstbalance_creation_dynamic(database, alarm_values):
        """
        Creation condition for BurstBalance metrics
        :return: if the metrics needs to be created or not
        """
        return re.fullmatch(alarm_values["MetricSpecifications"]["RegexType"], database["StorageType"]) is not None

    @staticmethod
    def cpucreditbalance_creation_dynamic(database, alarm_values):
        """
        Creation condition for CPUCreditBalance metrics
        :return: if the metrics needs to be created or not
        """
        return re.fullmatch(alarm_values["MetricSpecifications"]["RegexType"],
                            database["DBInstanceClass"].replace("db.", "")) is not None

    @staticmethod
    def dbconnections_threshold_dynamic(database, alarm_values):
        """
        Dynamic Threshold calculation for DBConnections metrics
        :return: Threshold value to be used
        """
        # Open json file with the mapping DBInstanceClass-MaxConnections
        # https://serverfault.com/questions/862387/aws-rds-connection-limits
        # https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.Managing.Performance.html

        # Extract instance type memory value (assuming EC2 and RDS' instance type match)
        client_for_instance_type = boto3.client("ec2", region_name=os.getenv("region"))
        try:
            instance_types = client_for_instance_type.describe_instance_types(
                InstanceTypes=[database["DBInstanceClass"].replace("db.", "")])["InstanceTypes"]
        except:
            print("Cry so loud because there is not match with that db instance size")
            # Threshold to 0 is force so that an alarm is raised for it. To set an acceptable value you have these
            #  options:
            #  - use DynamoDB
            #  - Do not run periodically this script
            #  - Remove the searching tag from resource
            return 0
        if len(instance_types) > 0:
            # The result from boto3 is in MiB. Needs to be converted in GiB
            # Reference table: https://sysadminxpert.com/aws-rds-max-connections-limit/
            db_GiB_size = instance_types[0]["MemoryInfo"]["SizeInMiB"] / 1024
        else:
            raise Exception(
                "Cry so loud because there is not match with that db instance size")

        # We evaluate threshold value based on AWS'formulas that worked on DB engine
        # https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Limits.html#RDS_Limits.MaxConnections
        maxconnection = 0
        divider = None
        db_byte_size = db_GiB_size * 1073741824
        if database["Engine"] in "aurora-mysql" or database["Engine"] in "aurora" or database["Engine"] in "mariadb" or \
                database["Engine"] in "mysql":
            divider = 12582880
            maxconnection = round(db_byte_size / divider)
            if maxconnection > 16000:
                maxconnection = 16000
        elif database["Engine"] in "oracle-ee" or database["Engine"] in "oracle-se2" or database[
            "Engine"] in "oracle-se":
            divider = 9868951
            least = 20000
            # Rounded formula: https://www.adamsmith.haus/python/answers/how-to-round-to-the-nearest-multiple-of-5-in-python
            maxconnection = round(db_byte_size / divider)
            if maxconnection < least:
                maxconnection = least
        elif database["Engine"] == "postgres" or database["Engine"] == "aurora-postgresql":
            divider = 9531392
            least = 5000
            # Rounded formula: https://www.adamsmith.haus/python/answers/how-to-round-to-the-nearest-multiple-of-5-in-python
            maxconnection = round(db_byte_size / divider)
            if maxconnection < least:
                maxconnection = least
        # Evaluate threshold based on integer static value set into default_values
        return maxconnection * (alarm_values["MetricSpecifications"]["Threshold"] / 100)

    @staticmethod
    def serverlesscapacity_creation_dynamic(database, alarm_values):
        """
        Creation condition for ServerlessCapacity metrics. It return true only if max_capacity > 1 and different from its min_capacity
        :return: if the metrics needs to be created or not
        """
        return database["ScalingConfigurationInfo"]["MaxCapacity"] > 1 and database["ScalingConfigurationInfo"][
            "MinCapacity"] != database["ScalingConfigurationInfo"]["MaxCapacity"]

    @staticmethod
    def serverlesscapacity_threshold_dynamic(database, alarm_values):
        """
        Dynamic Threshold calculation for ServerlessCapacity metrics
        :return: Threshold value to be used
        """
        return database["ScalingConfigurationInfo"]["MaxCapacity"] - alarm_values["MetricSpecifications"]["Threshold"]

    def __init__(self, database, cloudwatchclient, default_values):
        # Extract RDS' type (instance or cluster)
        dbtype = ""
        if "DBInstanceIdentifier" in database:
            dbtypedimension = "DBInstanceIdentifier"
            dbtype = "instance"
            dbidentifier = database["DBInstanceIdentifier"]
            dbarn = database["DBInstanceArn"]
        elif "DBClusterIdentifier" in database:
            dbtypedimension = "DBClusterIdentifier"
            dbtype = "cluster"
            dbidentifier = database["DBClusterIdentifier"]
            dbarn = database["DBClusterArn"]

        # Extract engine
        dbengine = database["Engine"]
        LOGGER.info(dbengine)

        # Extract engine mode (provisioned / serverless)
        dbenginemode = database.get("EngineMode", None)
        LOGGER.info(dbenginemode)

        # Extract available metrics for db engine
        metric_needed = {}
        for metric_name in default_values:
            db_engine_mode_check = True
            if dbenginemode is not None and "EngineModes" in default_values[metric_name]["MetricSpecifications"]:
                db_engine_mode_check = dbenginemode in default_values[
                    metric_name]["MetricSpecifications"]["EngineModes"]

            if dbtype in default_values[metric_name]["MetricSpecifications"]["Types"] and dbengine in \
                    default_values[metric_name]["MetricSpecifications"]["Engines"] and db_engine_mode_check:
                metric_needed[metric_name] = default_values[metric_name]

        # Invoke creation for extracted metrics
        for metric_name in metric_needed:
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchRDS, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    database, dbidentifier, dbarn, cloudwatchclient, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=f"{dbtype}-{dbidentifier}",
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchRDS,
                                            database,
                                            dbidentifier,
                                            dbarn,
                                            alarm_values,
                                            [{
                                                "Name": dbtypedimension,
                                                "Value": dbidentifier
                                            }],
                                            cloudwatchclient
                                            )
