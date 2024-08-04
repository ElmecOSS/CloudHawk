# ______________________________________________________
#  Author: Cominoli Luca, Dalle Fratte Andrea
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

# Import listing class

from cw_services.cw_acm import CloudWatchACM
from cw_services.cw_ebs import CloudWatchEBS
from cw_services.cw_ec2 import CloudWatchEC2
from cw_services.cw_efs import CloudWatchEFS
from cw_services.cw_eks import CloudWatchEKS
from cw_services.cw_elb import CloudWatchELB, CloudWatchELBTG
from cw_services.cw_os import CloudWatchOS
from cw_services.cw_rds import CloudWatchRDS
from cw_services.cw_vpn import CloudWatchVPN
from cw_services.cw_directconnect import CloudWatchDirectConnect
from cw_services.cw_dynamodb import CloudWatchDynamoDB
from cw_services.cw_elasticache import CloudWatchElastiCache
from cw_services.cw_fsx import CloudWatchFSx
from cw_services.cw_lambda import CloudWatchLambda
from cw_services.cw_globalaccelerator import CloudWatchGlobalAccelerator
from cw_services.cw_ecs import CloudWatchECS


class Callbacks:
    """
    Encapsulates callbacks after resource listing
    """

    @staticmethod
    def callback_acm(certificates_list, cloudwatchclient, default_values):
        for acm in certificates_list:
            CloudWatchACM(acm, cloudwatchclient, default_values)

    @staticmethod
    def callback_ebs(volumes_list, cloudwatchclient, default_values):
        for volume in volumes_list:
            CloudWatchEBS(volume, cloudwatchclient, default_values)

    @staticmethod
    def callback_ec2(instance_list, cloudwatchclient, default_values):
        for ec2 in instance_list:
            CloudWatchEC2(ec2, cloudwatchclient, default_values)

    @staticmethod
    def callback_efs(filesystem_list, cloudwatchclient, default_values):
        for efs in filesystem_list:
            CloudWatchEFS(efs, cloudwatchclient, default_values)

    @staticmethod
    def callback_eks(cluster_list, cloudwatchclient, default_values):
        for eks in cluster_list:
            CloudWatchEKS(eks, cloudwatchclient, default_values)

    @staticmethod
    def callback_elb(alb_list, nlb_list, cloudwatchclient, default_values_alb, default_values_nlb):
        for alb in alb_list:
            CloudWatchELB(alb, cloudwatchclient, default_values_alb)
        for nlb in nlb_list:
            CloudWatchELB(nlb, cloudwatchclient, default_values_nlb)

    @staticmethod
    def callback_elb_tg(alb_tg_list, nlb_tg_list, cloudwatchclient, default_values_alb_tg, default_values_nlb_tg):
        for elbtg in alb_tg_list:
            CloudWatchELBTG(elbtg, cloudwatchclient, default_values_alb_tg)
        for nlbtg in nlb_tg_list:
            CloudWatchELBTG(nlbtg, cloudwatchclient, default_values_nlb_tg)

    @staticmethod
    def callback_os(domains_list, cloudwatchclient, default_values):
        for os in domains_list:
            CloudWatchOS(os, cloudwatchclient, default_values)

    @staticmethod
    def callback_rds(database_list, cloudwatchclient, default_values):
        for rds in database_list:
            CloudWatchRDS(rds, cloudwatchclient, default_values)

    @staticmethod
    def callback_vpn(vpn_list, cloudwatchclient, default_values):
        for vpn in vpn_list:
            CloudWatchVPN(vpn, cloudwatchclient, default_values)

    @staticmethod
    def callback_directconnect(directconnect_list, cloudwatchclient, default_values):
        for directconnect in directconnect_list:
            CloudWatchDirectConnect(directconnect, cloudwatchclient, default_values)

    @staticmethod
    def callback_dynamodb(dynamodb_list, cloudwatchclient, default_values):
        for dynamodb in dynamodb_list:
            CloudWatchDynamoDB(dynamodb, cloudwatchclient, default_values)

    @staticmethod
    def callback_elasticache(elasticache_list, cloudwatchclient, default_values):
        for elasticache in elasticache_list:
            CloudWatchElastiCache(elasticache, cloudwatchclient, default_values)

    @staticmethod
    def callback_fsx(fsx_list, cloudwatchclient, default_values):
        for fsx in fsx_list:
            CloudWatchFSx(fsx, cloudwatchclient, default_values)

    @staticmethod
    def callback_lambda(lambda_list, cloudwatchclient, default_values):
        for lambda_item in lambda_list:
            CloudWatchLambda(lambda_item, cloudwatchclient, default_values)

    @staticmethod
    def callback_ecs(ecs_list, cloudwatchclient, default_values):
        for ecs_item in ecs_list:
            CloudWatchECS(ecs_item, cloudwatchclient, default_values)

    @staticmethod
    def callback_globalaccelerator(globalaccelerator_list, cloudwatchclient, default_values):
        for globalaccelerator in globalaccelerator_list:
            CloudWatchGlobalAccelerator(globalaccelerator, cloudwatchclient, default_values)
