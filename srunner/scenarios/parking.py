#!/usr/bin/env python
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
Parking scenario:
The scenario realizes the ego vehicle in a parking lot
and encountering a pedestrian and other static obstacles.
"""

from __future__ import print_function

import math
import py_trees
import carla

from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.scenarioatomics.atomic_behaviors import (ActorTransformSetter,
                                                                      ActorDestroy,
                                                                      AccelerateToVelocity,
                                                                      HandBrakeVehicle,
                                                                      KeepVelocity,
                                                                      StopVehicle)
from srunner.scenariomanager.scenarioatomics.atomic_criteria import CollisionTest
from srunner.scenariomanager.scenarioatomics.atomic_trigger_conditions import (InTriggerDistanceToLocationAlongRoute,
                                                                               InTimeToArrivalToVehicle,
                                                                               DriveDistance)
from srunner.scenariomanager.scenarioatomics.atomic_behaviors import Idle
from srunner.scenariomanager.timer import TimeOut
from srunner.scenarios.basic_scenario import BasicScenario
from srunner.tools.scenario_helper import get_location_in_distance_from_wp


class ParkingScenario(BasicScenario):

    """
    This class holds everything required for a parking lot scenario
    The ego vehicle is passing through the parking lot and encounters
    a pedestrian and other static obstalces.

    This is a single ego vehicle scenario
    """

    def __init__(self, world, ego_vehicles, config, randomize=False, debug_mode=False, criteria_enable=True,
                 timeout=200):
        """
        Setup all relevant parameters and create scenario
        """
        self._wmap = CarlaDataProvider.get_map()
        self._reference_transform = ego_vehicles[0].get_transform()

        # ego vehicle parameters
        self._ego_vehicle_distance_driven = 40

        # other vehicle parameters
        self._other_actor_target_velocity = 4
        self._other_actor_max_brake = 1.0

        # Timeout of scenario in seconds
        self.timeout = timeout

        super(ParkingScenario, self).__init__("ParkingScenario",
                                                       ego_vehicles,
                                                       config,
                                                       world,
                                                       debug_mode,
                                                       criteria_enable=criteria_enable)

    def _initialize_actors(self, config):
        """
        Custom initialization
        """

        actors_info = {'walker.*': {'yaw': 270, 'k': 10, 'j': 5, 'z':0},
                       'static.prop.container': {'yaw': 90, 'k': 25, 'j': 0, 'z': 0},
                       'static.prop.shoppingcart': {'yaw': 0, 'k': 2, 'j': 15, 'z': 2}}

        for actor_name, actor_transform in actors_info.items():
            self.spawn_actor(actor_name, actor_transform, self._reference_transform)

    def spawn_actor(self, actor_name, actor_transform, start_transform):
        """
        Spawn Pedestrian and Obstacles
        """
        transform = carla.Transform(
                start_transform.location,
                start_transform.rotation)

        _perp_angle = 90

        transform.location += actor_transform['k'] * transform.rotation.get_forward_vector()
        transform.rotation.yaw += _perp_angle
        transform.location += actor_transform['j'] * transform.rotation.get_forward_vector()
        transform.rotation.yaw = start_transform.rotation.yaw + actor_transform["yaw"]
        transform.location.z += actor_transform['z']

        actor = CarlaDataProvider.request_new_actor(
                actor_name, transform)
        actor.set_simulate_physics(True)
        self.other_actors.append(actor)


    def _create_behavior(self):
        """
        Only behavior here is to wait
        """
        ego_stand = Idle(60)

        _dist_to_trigger = 5
        _dist_actor_travel = 10
        _time_to_reach = 5

        scenario_sequence = py_trees.composites.Sequence()

        # leaf nodes
        start_condition = InTimeToArrivalToVehicle(self.ego_vehicles[0],
                                                   self.other_actors[0],
                                                   _time_to_reach)

        actor_velocity = KeepVelocity(self.other_actors[0],
                                      self._other_actor_target_velocity,
                                      name="walker velocity")
        actor_drive = DriveDistance(self.other_actors[0],
                                    _dist_actor_travel,
                                    name="walker drive distance")
        actor_stop_crossed_lane = StopVehicle(self.other_actors[0],
                                              self._other_actor_max_brake,
                                              name="walker stop")

        # non leaf nodes

        scenario_sequence = py_trees.composites.Sequence()
        keep_velocity = py_trees.composites.Parallel(
            policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE, name="keep velocity other")

        # building tree
        scenario_sequence.add_child(start_condition)
        scenario_sequence.add_child(actor_velocity)
        scenario_sequence.add_child(actor_drive)
        scenario_sequence.add_child(actor_stop_crossed_lane)
        scenario_sequence.add_child(ego_stand)
        return scenario_sequence

    def _create_test_criteria(self):
        """
        A list of all test criteria will be created that is later used
        in parallel behavior tree.
        """
        criteria = []

        collision_criterion = CollisionTest(self.ego_vehicles[0])
        criteria.append(collision_criterion)

        return criteria

    def __del__(self):
        """
        Remove all actors upon deletion
        """
        self.remove_all_actors()
