#!/usr/local/bin/python3
import os
import logging
from pprint import pformat
from pyroute2 import IPRoute
from pyroute2.netlink.exceptions import NetlinkError
from time import sleep


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-1s %(levelname)-1s [%(threadName)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class RouteManagerEnvVariables(object):
    '''Parse the environment variables'''
    def __init__(self, dict_env:dict = None):
        """Constructor with real environment variables"""
        super().__init__()
        self.dict_env = dict_env
        #self.mode = self.enviro().get("MODE")
        self.secondary_interface = self.enviro().get("SECONDARY_INTERFACE")
        self.secondary_gateway = self.enviro().get("SECONDARY_GW")
        self.bgp_svc_subnets = self.enviro().get("BGP_SVC_SUBNETS")
        if self.bgp_svc_subnets is not None:
            try:
                self.bgp_svc_subnets = set(self.bgp_svc_subnets.split(','))
            except:
                logger.error("Could not parse the BGP_SVC_SUBNETS expected forma is a comma separated list")
                exit(1)
        self.rt_number = int(self.enviro().get("RT_NUMBER"))

        logger.info("Parsed Environment Variables %s", pformat(vars(self)))

    def enviro(self):
        '''Return the Dictionary with all the Environment Variables'''
        if self.dict_env is None:
            return os.environ
        else:
            return self.dict_env

class RouteManager(object):
    '''What we need to do here is pretty simple: 
        - Add a default GW to the Service BD or L3OUT Secondary Address in a dedicated route table
        - Ensure Traffic sourced from the K8s Nodes is using the new route table
        - Ensure Traffic sourced from the Service Subnet (only needed for BGP) is using the new route table
    '''
    def __init__(self, env:RouteManagerEnvVariables) -> None:
        super().__init__()
        self.env = env
        self.ipr = IPRoute()
    def get_interface_address(self):

        address = self.ipr.get_addr(label=self.env.secondary_interface)
        if len(address) < 1:
            logger.error("Secondary Interface %s configured with more than 1 address, this is unsupported. Detected Config:\n%s", self.env.secondary_interface, pformat(address) )
        else:
            addr = address[0].get_attr('IFA_ADDRESS')
            return addr
            #prefix = address[0]['prefixlen']

    def sync_routes(self):
        #logger.info("Sync routes to gw %s", self.env.secondary_gateway)
        current_routes = self.get_routes()
        expected_routes = set()
        expected_routes.add("0.0.0.0/0," + self.env.secondary_gateway)

        routes_to_add = expected_routes - current_routes
        routes_to_remove = current_routes - expected_routes
        if not routes_to_remove and not routes_to_add:
            logger.info("Routes are in sync, nothing to do")
        else:
            for route in routes_to_remove:
                dst, gw = route.split(',')
                logger.info("Removing route %s %s", dst, gw)
                self.ipr.route("del", dst=dst, gateway=gw, table=self.env.rt_number)

            for route in routes_to_add:
                dst, gw = route.split(',')
                logger.info("Adding route %s %s", dst, gw)
                self.ipr.route("add", dst=dst, gateway=gw, table=self.env.rt_number)
        
    def get_routes(self):
        rt_set = set()
        routes = self.ipr.get_routes(table=self.env.rt_number)
        for route in routes:
            # If there is no RTA_DST then is a default route
            if not route.get_attr('RTA_DST'):
                rt_set.add("0.0.0.0/0," + route.get_attr('RTA_GATEWAY'))
            else:
                #At the moment I am only adding default so this could should never be executed
                rt_set.add(route.get_attr('RTA_DST') + route.get_attr('RTA_GATEWAY'))
                logger.warning("Detected unexpected routes the code is not tested for this %s %s", route.get_attr('RTA_DST'), route.get_attr('RTA_GATEWAY'))
        return rt_set
    
    def get_rules(self):
        rules_set = set()
        rules = self.ipr.get_rules(table=self.env.rt_number)
        for rule in rules:
            rules_set.add(rule.get_attr('FRA_SRC') + '/' + str(rule['src_len']))
        return rules_set

    def sync_rules(self):
        current_rules = self.get_rules()
        expected_rules = set()
        expected_rules.add(self.get_interface_address() + '/' + '32')
        if self.env.bgp_svc_subnets:
            expected_rules = expected_rules.union(self.env.bgp_svc_subnets)
        rules_to_add = expected_rules - current_rules
        rules_to_remove = current_rules - expected_rules

        if not rules_to_add and not rules_to_remove:
            logger.info("Rules are in sync, nothing to do")
        else:
            for rule in rules_to_remove:
                src, src_len = rule.split('/')
                logger.info("Removing rule %s/%s", src, src_len)
                self.ipr.rule('del',
                                table=self.env.rt_number,
                                src=src,
                                src_len=int(src_len))
            for rule in rules_to_add:
                src, src_len = rule.split('/')
                logger.info("Adding rule %s/%s", src, src_len)
                self.ipr.rule('add',
                                table=self.env.rt_number,
                                src=src,
                                src_len=int(src_len))


        
env = RouteManagerEnvVariables()
rm = RouteManager(env)
while True:
    rm.sync_routes()
    rm.sync_rules()
    '''
    At the moment the loop is most likely useless because unless someone manually mess up the routes 
    no changes are expected and if the DaemonSet config is changed the DS is restarted anyway however by having this
    loop I am potentially ready to pull the route information from the APIC directly and make it a bit more self configuring
    '''
    logger.info("Will check again in 60s")
    sleep(60)
