import time
import pickle
from common import *
from math import *
from copy import copy
from OpenNero import *
from KeyboardAgent import KeyboardAgent

class AgentState:
    """
    State that we keep for each agent
    """
    def __init__(self):
        self.position = Vector3f(0, 0, 0)
        self.rotation = Vector3f(0, 0, 0)
        self.velocity = Vector3f(0, 0, 0)
        self.orig_position = Vector3f(0, 0, 0)
        self.initial_position = Vector3f(0, 0, 0)
        self.initial_rotation = Vector3f(0, 0, 0)
        self.initial_velocity = Vector3f(0, 0, 0)
        self.goal_reached = False
        self.has_new_advice = False
        self.current_step = 0
        self.current_episode = 0
        self.time = time.time()
        self.start_time = self.time
        self.visited_cubes = set()

class AgentTrace:
    """
    Class for storing the trace of an agent
    """
    def __init__(self):
        self.initial_step = None
        self.position = []
        self.rotation = []
        self.velocity = []
        self.sensors = []
        self.actions = []

    def print_trace(self, filename):
        with open(filename, 'w') as file:
            for i in range(len(self.position)):
                file.write(str([self.position[i].x, self.position[i].y, self.position[i].z]))
                file.write(str([self.rotation[i].x, self.rotation[i].y, self.rotation[i].z]))
                file.write(str([self.velocity[i].x, self.velocity[i].y, self.velocity[i].z]))
            for i in range(len(self.sensors)):
                file.write(str(self.sensors[i]))
                file.write(str(self.actions[i]))


class ForageEnvironment(Environment):
    VELOCITY = 1.1 # max velocity of agent in one step
    ANGULAR_VELOCITY = 5. # max angles in degrees agent can turn in one step
    ACCELERATION = 0.005 # max acceleration of agent in one step
    DRAG_CONST = 0.005 # constant for calculating drag
    TIME_PER_STEP = 0.01 # min time between steps in seconds
    STEPS_PER_EPISODE = 600 # max number of steps per episode
    MAX_DISTANCE = 1000000 # max possible distance of objects from agent
    MIN_DISTANCE = 1 # min distance from object for agent to visit it

    """
    controller environment for the foraging experiment
    """
    def __init__(self, server):
        """
        Create the environment
        """
        Environment.__init__(self) 

        self.server = server
        
        self.states = {}           # dictionary from agents to their states in the environment
        self.cubes = set()         # ids of cubes in the environment
        self.active_cubes = set()  # ids of cubes that simulation can see
        self.walls = set()         # ids of walls in the environment
        self.active_walls = set()  # ids of walls that simulation can see
        self.object_paths = dict() # dictionary containing any user-specified object paths
        self.num_sensors = server.num_sensors
        self.num_actions = server.num_outputs
        
        abound = FeatureVectorInfo()
        sbound = FeatureVectorInfo()
        rbound = FeatureVectorInfo()
                
        # actions
        for i in range(self.num_actions):
            abound.add_continuous(-0.5, 0.5)
        
        # sensors
        for i in range(self.num_sensors):
            sbound.add_continuous(-1, 1)
    
        # rewards
        rbound.add_continuous(-1, 1)
        
        self.agent_info = AgentInitInfo(sbound, abound, rbound)

        self.tracing = False             # indicates if the agents are being traced
        self.simdisplay = True           # indicates if the simulation of agents is being displayed
        self.trace = None                # trace of agents
        self.use_trace = False           # use loaded trace for calculating reward
        self.run_backprop = False        # whether to run backprop if trace is loaded
        self.path_markers_trace = []     # ids of objects used to mark path of trace
        self.path_markers_champ = []     # ids of objects used to mark path of champ
        self.bbmarkers = []


    def initialize(self):
        # newly added objects are made active only between episodes
        # to prevent problems.
        self.active_cubes = copy(self.cubes)
        self.active_walls = copy(self.walls)

    def remove_object(self, oid):
        # remove the object if it is a wall or cube
        if oid in self.cubes:
            self.cubes.remove(oid)
        if oid in self.active_cubes:
            self.active_cubes.remove(oid)
        if oid in self.walls:
            self.walls.remove(oid)            
        if oid in self.active_walls:
            self.active_walls.remove(oid)

    def start_tracing(self):
        # create trace object and start tracing
        # tracing of only one agent is currently supported
        if not self.tracing and len(self.states) == 1:
            print "starting trace..."
            self.trace = AgentTrace()
            self.tracing = True

    def stop_tracing(self):
        # stop tracing the agent
        print "stopping trace..."
        self.tracing = False

    def save_trace(self, filename):
        # pickle the current trace in the given file
        print "saving trace..."
        with open(filename, 'w') as file:
            pickle.dump(self.trace, file)

    def load_trace(self, filename):
        # load previously pickled trace from the given file
        print "loading trace..."
        with open(filename, 'r') as file:
            self.trace = pickle.load(file)
        self.use_trace = True
        for i in range(len(self.trace.position)):
            self.path_markers_trace.append(getSimContext().getNextFreeId())
            addObject("data/shapes/cube/YellowCube.xml", position=self.trace.position[i], rotation=Vector3f(0,0,0), scale=Vector3f(0.25,0.25,0.25))

    def unload_trace(self):
        # unload previously loaded trace
        print "unloading trace..."
        self.trace = None
        self.use_trace = False
        while len(self.path_markers_trace) > 0:
            getSimContext().removeObject(self.path_markers_trace.pop())

    def get_agent_info(self, agent):
        """ return a blueprint for a new agent """
        return self.agent_info

    def get_new_state(self):
        """ return a new agent state """
        return AgentState()
    
    def get_state(self, agent):
        if agent not in self.states:
            self.states[agent] = AgentState()
            print "new state created"
        state = self.states[agent]
        if state.current_step == 0:
            state.orig_position = agent.state.position
            state.initial_position = agent.state.position
            state.initial_rotation = agent.state.rotation
            state.initial_velocity = agent.state.velocity
            state.position = state.initial_position
            state.rotation = state.initial_rotation
            state.velocity = state.initial_velocity
        return state
    
    def reset(self, agent):
        """
        reset the environment to its initial state
        """
        state = self.get_state(agent)
        state.position = state.initial_position
        state.rotation = state.initial_rotation
        state.velocity = state.initial_velocity
        state.orig_position = state.initial_position
        agent.state.position = state.initial_position
        agent.state.rotation = state.initial_rotation
        agent.state.velocity = state.initial_velocity
        state.goal_reached = False
        state.has_new_advice = False
        state.current_step = 0
        state.current_episode += 1
        state.visited_cubes = set()
        agent.state.color = Color(0, 255, 255, 255)

        self.active_cubes = copy(self.cubes)
        self.active_walls = copy(self.walls)
        while len(self.path_markers_champ) > 0:
            getSimContext().removeObject(self.path_markers_champ.pop())

        print "Episode %d complete" % state.current_episode
        return True
    
    def step(self, agent, actions):
        """
        A step for an agent
        """
        state = self.get_state(agent)

        # convert actions because pickling not enabled for its datatype (DoubleVector)
        if self.tracing:
            self.trace.actions.append([a for a in actions])
        
        state.position = agent.state.position
        state.rotation = agent.state.rotation
        state.velocity = agent.state.velocity

        reward = 0
        if self.perform_actions(state, actions):
            agent.state.position = state.position
            agent.state.rotation = state.rotation
            agent.state.velocity = state.velocity

            reward = self.calculate_reward(state)

        #print "actions: ", actions
        state.current_step += 1
        return reward

    def calculate_reward(self, state):
        """ calculate reward for the given state """
        # Find the closest cube that has not yet been visited.
        closest_cube_dist = self.MAX_DISTANCE
        closest_cube_id = 0
        reward = 0
        for cid in self.active_cubes:
            if cid not in state.visited_cubes:
                dist = getSimContext().getObjectPosition(cid).getDistanceFrom(state.position)
                if dist < closest_cube_dist:
                    closest_cube_dist = dist
                    closest_cube_id = cid

        # Calculate reward
        if closest_cube_dist < self.MIN_DISTANCE:  # Agent visits the cube if it is close enough.
            reward = 1
            state.visited_cubes.add(closest_cube_id)
            state.orig_position = state.position
        elif closest_cube_dist < self.MAX_DISTANCE:    # Reward based on how close agent is to the cube.
            closest_cube_orig_dist = getSimContext().getObjectPosition(closest_cube_id).getDistanceFrom(state.orig_position)
            reward = 1 - (closest_cube_dist/closest_cube_orig_dist)
            if reward < -1:
                reward = -1
        #else:                                          # No more cubes to visit.
        #    state.goal_reached = True

        return reward
    

    def perform_actions(self, state, actions):
        """ perform the actions, given the state of the agent; returns true if the
        state is updated """

        # Make a deep copy of the current position, rotation, and velocity
        # so that the variables can be modified without affecting the state.
        position = Vector3f(state.position.x, state.position.y, state.position.z)
        rotation = Vector3f(state.rotation.x, state.rotation.y, state.rotation.z)
        velocity = Vector3f(state.velocity.x, state.velocity.y, state.velocity.z)

        # Polar coordinates (i.e. distance, orientation [-ANGLE, ANGLE])
        dpos = fabs(actions[0])*self.VELOCITY
        dtheta = actions[1]*2*self.ANGULAR_VELOCITY
        rotation.z += dtheta
        position.x += dpos*cos(radians(rotation.z))
        position.y += dpos*sin(radians(rotation.z))

        # The action takes effect only if the agent does not collide with any walls
        # while moving to the new position.
        collided = False
        for wid in self.active_walls:
            if getSimContext().findInRay(state.position, position, 0, False):
                collided = True
                break

        if not collided:
            # Update the position, velocity, and rotation of the agent.
            state.position = position
            state.rotation = rotation
            state.velocity = velocity
            return True
        else:
            return False

    
    def sense(self, agent):
        """ figure out what the agent should sense """
        state = self.get_state(agent)
        sensors = self.compute_sensors(state)

        # convert sensors because pickling not enabled for its datatype (DoubleVector)
        if self.tracing:
            if self.trace.initial_step == None:  # record the initial time step
                self.trace.initial_step = state.current_step
            self.trace.position.append(state.position)
            self.trace.rotation.append(state.rotation)
            self.trace.velocity.append(state.velocity)
            self.trace.sensors.append([s for s in sensors])

        if hasattr(agent, 'index') and agent.index == 0 and state.current_episode > 0:
            self.path_markers_champ.append(getSimContext().getNextFreeId())
            addObject("data/shapes/cube/BlueCube.xml", position=state.position, rotation=Vector3f(0,0,0), scale=Vector3f(0.25,0.25,0.25))

        if isinstance(agent, KeyboardAgent):
            self.path_markers_champ.append(getSimContext().getNextFreeId())
            addObject("data/shapes/cube/YellowCube.xml", position=state.position, rotation=Vector3f(0,0,0), scale=Vector3f(0.25,0.25,0.25))

        return sensors

    def compute_sensors(self, state):
        """ compute the sensor readings of an agent, given its current state """
        # First, update the positions of any moving objects in the environment
        for oid, path in self.object_paths.items():
            [x, y, z] = eval(path)(state.current_step)
            getSimContext().setObjectPosition(oid, Vector3f(x, y, z))

        sensors = self.agent_info.sensors.get_instance()
        for i in range(0, self.num_sensors):
            sensors[i] = 0

        num_cube_sensors = len(self.server.cube_sensor_angles)

        # Normalize angle representing agent orientation to lie in the range [0, 360)
        agent_angle = state.rotation.z - floor(state.rotation.z/360)*360

        # Find maximum distance of cubes from the agent.  This maximum distance is used
        # to normalize the distances.  Also, store distances and angles for use below.
        maxdist = 0
        cubedst = []
        cubeang = []
        for cid in self.active_cubes:
            # Sensors detect the cube only if it has not yet been visited by the agent.
            if cid not in state.visited_cubes:
                cube_position = getSimContext().getObjectPosition(cid)
                dist = cube_position.getDistanceFrom(state.position)
                maxdist = max(maxdist, dist)

                cube_angle = degrees(atan2(cube_position.y - state.position.y, cube_position.x - state.position.x))
                cube_angle = cube_angle - floor(cube_angle/360)*360  # range [0, 360)
                angle = cube_angle - agent_angle  # range (-360, 360)
                if angle > 180: angle = angle - 360
                if angle < -180: angle = angle + 360  # range [-180, 180]
                angle = angle/180. # range [-1, 1]

                cubedst.append(dist)
                cubeang.append(angle)

        # Increase maxdist to represent infinity.  This maxdist is also used for calculating
        # wall sensor activations.
        maxdist *= 1.1

        # There is a sensor in each quadrant of the egocentric coordinate frame of the agent.
        # Each cube activates a given sensor by an amount equal to the value of the triangle
        # function centered on the cube at the location of the sensor in proportion to the
        # distance of the cube from the agent.
        for i in range(len(cubedst)):
            dist = cubedst[i]/maxdist
            angle = cubeang[i]

            for j in range(num_cube_sensors):
                sensors[j] += (1-dist)*self.triangle_activation(angle, self.server.cube_sensor_angles[j], 0.25)

        # Normalize the sensor values to [-1, 1]
        maxval = max([sensors[i] for i in range(num_cube_sensors)])
        minval = min([sensors[i] for i in range(num_cube_sensors)])
        if maxval != minval:
            for i in range(num_cube_sensors):
                sensors[i] = ((sensors[i]-minval)/(maxval-minval))*2 - 1
        else:
            for i in range(num_cube_sensors):
                sensors[i] = minval

        # The next sensors detect the closest walls (i.e. those that produce maximum activation).
        num_wall_sensors = len(self.server.wall_sensor_angles)
        for wid in self.active_walls:
            # Get the min and max points of the bounding box of the wall before transformation.
            wbbmin = getSimContext().getObjectBBMinEdge(wid)
            wbbmax = getSimContext().getObjectBBMaxEdge(wid)

            # Find points on the four corners of the wall after transformation.
            corners = [getSimContext().transformVector(wid, Vector3f(wbbmin.x, wbbmin.y, 0)),
                       getSimContext().transformVector(wid, Vector3f(wbbmax.x, wbbmax.y, 0)),
                       getSimContext().transformVector(wid, Vector3f(wbbmin.x, wbbmax.y, 0)),
                       getSimContext().transformVector(wid, Vector3f(wbbmax.x, wbbmin.y, 0))]

            # Find min and max angles of the wall corner points with respect to agent position.
            wall_angle_min = 361
            wall_angle_max = -1
            for i in range(4):
                wall_angle = degrees(atan2(corners[i].y - state.position.y, corners[i].x - state.position.x))
                wall_angle = wall_angle - floor(wall_angle/360)*360  # range [0, 360)
                if wall_angle < wall_angle_min:
                    wall_angle_min = wall_angle
                    wall_point_min = corners[i]
                if wall_angle > wall_angle_max:
                    wall_angle_max = wall_angle
                    wall_point_max = corners[i]

            wall_angle_diff = wall_angle_max - wall_angle_min

            # Iterate through all wall sensors
            for j in range(num_wall_sensors):
                sensor_angle = agent_angle + self.server.wall_sensor_angles[j]*180
                sensor_angle = sensor_angle - floor(sensor_angle/360)*360  # range [0, 360)

                # If sensor is oriented between the extreme points of the wall, then angle is 0
                # and a ray along the sensor orientation from the agent will intersect the wall;
                # otherwise find angle to the extreme point that is closer in angular distance.
                # For this we find the angle subtended by the wall at the position of the agent.
                # There are two cases to consider: difference between the min and max wall angles
                # is (1) less than 180 degrees (angle subtended is this difference), and
                # (2) greater than 180 degrees (angle subtended is 360 - this difference).
                if ((wall_angle_diff < 180 and (wall_angle_min <= sensor_angle and sensor_angle <= wall_angle_max)) or
                    (wall_angle_diff > 180 and (sensor_angle <= wall_angle_min or sensor_angle >= wall_angle_max))):
                    ray_start = state.position
                    ray_end = Vector3f(state.position.x + self.MAX_DISTANCE*cos(radians(sensor_angle)),
                                       state.position.y + self.MAX_DISTANCE*sin(radians(sensor_angle)),
                                       state.position.z)
                    intersection = Vector3f(0,0,0)
                    if getSimContext().findInRay(ray_start, ray_end, 0, False):
                        dist = intersection.getDistanceFrom(state.position)
                        if dist > maxdist: dist = maxdist   # wall farther than the farthest cube
                        dist = dist/maxdist if maxdist > 0 else 1.0
                        angle = 0
                        activation = 1-dist
                        sensors[num_cube_sensors+j] = max(sensors[num_cube_sensors+j], activation)
                else:
                    # Sensor is oriented outside the angle subtended by the wall.
                    if wall_angle_diff < 180:
                        # Transform sensor angle to eliminate the discontinuity at 360 degrees.
                        if sensor_angle < wall_angle_min:
                            sensor_angle_tmp = sensor_angle + 360
                        else:
                            sensor_angle_tmp = sensor_angle
                        # Transform min wall angle to eliminate discontinuity at 360 degrees.
                        wall_angle_min_tmp = 360 - wall_angle_diff + wall_angle_max
                        # Now we check which side of the wall the sensor is closer to in terms
                        # of angular distance.
                        if sensor_angle_tmp < (wall_angle_max + wall_angle_min_tmp)/2:
                            # sensor closer to max angle side of wall
                            wall_position = Vector3f(wall_point_max.x, wall_point_max.y, state.position.z)
                            angle = wall_angle_max - sensor_angle  # range (-360, 360)
                        else:
                            # sensor closer to min angle side of wall
                            wall_position = Vector3f(wall_point_min.x, wall_point_min.y, state.position.z)
                            angle = wall_angle_min - sensor_angle  # range (-360, 360)
                    else:
                        # No need to transform angles because sensor angle lies numerically
                        # between min and max wall angles.
                        if sensor_angle < (wall_angle_min + wall_angle_max)/2:
                            # sensor closer to min angle side of wall
                            wall_position = Vector3f(wall_point_min.x, wall_point_min.y, state.position.z)
                            angle = wall_angle_min - sensor_angle  # range (-360, 360)
                        else:
                            # sensor closer to max angle side of wall
                            wall_position = Vector3f(wall_point_max.x, wall_point_max.y, state.position.z)
                            angle = wall_angle_max - sensor_angle  # range (-360, 360)
         
                    dist = wall_position.getDistanceFrom(state.position)
                    if dist > maxdist: dist = maxdist   # wall farther than the farthest cube
                    dist = dist/maxdist if maxdist > 0 else 1.0
                    if angle > 180: angle = angle - 360
                    if angle < -180: angle = angle + 360
                    angle = angle/180. # range [-1, 1]
                    activation = (1-dist)*self.triangle_activation(angle, self.server.wall_sensor_angles[j], self.server.wall_sensor_hbases[j])
                    sensors[num_cube_sensors+j] = max(sensors[num_cube_sensors+j], activation)

        # Make wall sensor values either 0 or 1.
        for i in range(num_wall_sensors):
            sensors[num_cube_sensors+i] = ceil(sensors[num_cube_sensors+i])

        # Convert sensor values to [-1, 1]; -1 indicates sensor does not detect wall.
        #for i in range(num_wall_sensors):
        #    if sensors[num_cube_sensors+i] == 0.0:
        #        sensors[num_cube_sensors+i] = -1.0

        # the last sensor is the bias
        sensors[-1] = 1

        #print "sensors: ", sensors
        return sensors

    def triangle_activation(self, c, x, b):
        """
        evaluate triangle function at the point x with the given center c;
        b is half base of the triangle. range for x and c is [-1, 1] and
        that for b is (0, 1].
        """
        p = 2.    # period of the function (since range of x is [-1, 1])
        h = 1.    # height of the triangle

        # First make sure x is in range for the computation below
        if x < c-p+b:
            x = x+p
        elif x > c+p-b:
            x = x-p

        # Find point on triangle centered at c and between c-b and c+b
        if x <= c and x > c-b:
            y = (x-c+b)*h/b
        elif x > c and x < c+b:
            y = (c+b-x)*h/b
        else:
            y = 0

        return y

        
    def is_active(self, agent):
        """ return true when the agent should act """
        #state = self.get_state(agent)
        #if time.time() - state.time > self.TIME_PER_STEP:
        #    state.time = time.time()
        #    return True
        #else:
        #    return False
        return True
        
    def is_episode_over(self, agent):
        state = self.get_state(agent)
        if self.simdisplay == False:
            return True
        elif self.STEPS_PER_EPISODE != 0 and state.current_step >= self.STEPS_PER_EPISODE:
            #self.stop_tracing()
            #self.save_trace("auto.trace")
            #self.start_tracing()
            return True
        elif state.goal_reached:
            return True
        elif state.has_new_advice:  # restart episode if agent has new advice
            return True
        else:
            return False
    
    def cleanup(self):
        """
        This is the way the World ends
        """
        pass

