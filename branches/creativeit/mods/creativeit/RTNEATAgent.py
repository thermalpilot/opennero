from math import *
from OpenNero import *
import random
import creativeit

class RTNEATAgent(AgentBrain):
    INDEX_COUNT = 0
    BACKPROP_WINDOW_SIZE = 10
    ERROR_THRESHOLD = 5

    """
    rtNEAT agent
    """
    def __init__(self):
        """
        Create an agent brain
        """
        # this line is crucial, otherwise the class is not recognized as an AgentBrainPtr by C++
        AgentBrain.__init__(self)
        self.rtneat = get_ai("neat")
        self.org = None
        self.environment = creativeit.module.getMod().environment
        self.passed_steps = 0

    def initialize(self, init_info):
        """
        Initialize an agent brain with action and sensor information
        """
        self.actions = init_info.actions # constraints for actions
        self.sensors = init_info.sensors # constraints for sensors
        return True

    def start(self, time, sensors):
        """
        start of an episode
        """
        # Index is assigned here instead of in initialize() because it is here that
        # we get an rtneat organism for the agent.  The index is reassigned at the
        # start of every episode because the organism changes in every episode.
        self.index = RTNEATAgent.INDEX_COUNT
        RTNEATAgent.INDEX_COUNT = (RTNEATAgent.INDEX_COUNT+1) % creativeit.module.getMod().pop_size

        self.org = self.rtneat.next_organism(self.org)
        self.net = self.org.net
        self.net.flush()
        self.reward = 0
        self.reward_steps = 0
        self.reward_steps_total = 0
        self.org.fitness = 0
        #if self.index == 0:  # Color the elite organism
        #    self.sim.color = Color(0, 200, 28, 56)
        #print "got network to evaluate: " + str(self.net)
        if self.index == 0:
            self.net.print_links()
        return self.network_action(sensors)

    def act(self, time, sensors, reward):
        """
        a state transition
        """
        # Store fitness if a cube was collected, otherwise accumulate reward.
        if reward >= 1:
            self.org.fitness += reward
            self.reward = 0
            self.reward_steps_total += self.reward_steps
            self.reward_steps = 0
        else:
            self.reward += reward
            self.reward_steps += 1
        return self.network_action(sensors) # return action

    def end(self, time, reward):
        """
        end of an episode
        """
        # if simulation display has been turned off, complete the episode here
        if self.environment.simdisplay == False:
            state = self.environment.get_state(self)
            while state.current_step < self.environment.STEPS_PER_EPISODE and self.environment.is_active(self):
                sensors = self.environment.compute_sensors(state)
                actions = self.act(time, sensors, reward)
                reward = self.environment.calculate_reward(state) if self.environment.perform_actions(state, actions) else 0.0
                state.current_step += 1

        # store last reward and add average reward to fitness (i.e. how good the agent was since
        # collecting the last cube)
        self.reward += reward
        self.reward_steps += 1
        if self.reward != 0:  # note that reward can be negative
            self.org.fitness += self.reward/self.reward_steps
            self.reward_steps_total += self.reward_steps
        # increase fitness based on how quickly cubes were collected
        self.org.fitness += 1.0/self.reward_steps_total if self.reward_steps_total > 0 else 0.0
        self.org.time_alive += 1

        # if a trace has been loaded, then process it here
        if self.environment.use_trace:
            trfitness = self.evaluate_trace()  # Calculate fitness and passed steps
            # Run backprop and update if not the elite organism and backprop is enabled
            if self.index != 0 and self.environment.run_backprop:
                self.backprop_trace()
                trfitness = self.evaluate_trace()  # Calculate fitness and passed steps
            self.org.fitness = floor(self.org.fitness if self.org.fitness > 0.0 else 0.0) + trfitness
            print "index: %d, final reward: %f, trace fitness: %f, fitness: %f" % (self.index, reward, trfitness, self.org.fitness)
        else:
            print "index: %d, final reward: %f, fitness: %f" % (self.index, reward, self.org.fitness)

        return True

    def destroy(self):
        """
        the agent brain is discarded
        """
        return True
        
    def network_action(self, sensors):
        """
        Take the current network
        Feed the sensors into it
        Activate the network to produce the output
        Collect and interpret the outputs as valid actions
        """
        assert(len(sensors) == creativeit.module.getMod().num_sensors) # make sure we have the right number of sensors
        inputs = [sensor for sensor in sensors] # create the sensor array
        self.net.load_sensors(inputs)
        self.net.activate()
        outputs = self.net.get_outputs()

        if self.index == 0:
            print "agent 0 inputs: ", inputs
            print "agent 0 outputs: ", outputs
            self.net.show_activation()

        actions = self.actions.get_instance() # make a vector for the actions

        assert(len(actions) == len(outputs))
        for i in range(len(outputs)):
            actions[i] = outputs[i] - 0.5
            # make actions discrete, e.g. -0.4, -0.3, ... 0.3, 0.4
            #discretization = 20.0
            #if actions[i] > 0:
            #    actions[i] = floor(actions[i]*discretization)/discretization
            #else:
            #    actions[i] = ceil(actions[i]*discretization)/discretization

        return actions

    def evaluate_trace(self):
        """
        evaluate agent and compute fitness based on trace information
        """
        self.net.flush()
        state = self.environment.get_new_state()
        trace = self.environment.trace
        state.position = Vector3f(trace.position[0].x, trace.position[0].y, trace.position[0].z)
        state.rotation = Vector3f(trace.rotation[0].x, trace.rotation[0].y, trace.rotation[0].z)
        state.velocity = Vector3f(trace.velocity[0].x, trace.velocity[0].y, trace.velocity[0].z)
        state.current_step = trace.initial_step
        j = 0  # trace index at which error is calculated
        while j < len(trace.position)-1 and state.current_step < self.environment.STEPS_PER_EPISODE:
            sensors = self.environment.compute_sensors(state)
            actions = self.network_action(sensors)
                    
            # error based on position - find index in trace where error based on
            # current position starts to increase, i.e. starting with the current
            # trace index, we find position in trace that is closest to the current
            # state position.
            error1 = trace.position[j].getDistanceFrom(state.position)
            error2 = trace.position[j+1].getDistanceFrom(state.position)
            while error1 >= error2 and j < len(trace.position)-2:
                j += 1
                error1 = error2
                error2 = trace.position[j+1].getDistanceFrom(state.position)

            if error1 > self.ERROR_THRESHOLD:
                break

            # calculate new position, orientation, and velocity
            self.environment.perform_actions(state, actions)
            state.current_step += 1

        self.passed_steps = j
        return float(j)/len(trace.position)


    def backprop_trace(self):
        """
        adjust network weights using backprop and position information in the trace
        """
        self.net.flush()
        state = self.environment.get_new_state()
        trace = self.environment.trace
        state.position = Vector3f(trace.position[self.passed_steps].x, trace.position[self.passed_steps].y, trace.position[self.passed_steps].z)
        state.rotation = Vector3f(trace.rotation[self.passed_steps].x, trace.rotation[self.passed_steps].y, trace.rotation[self.passed_steps].z)
        state.velocity = Vector3f(trace.velocity[self.passed_steps].x, trace.velocity[self.passed_steps].y, trace.velocity[self.passed_steps].z)
        state.current_step = trace.initial_step + self.passed_steps
        i = self.passed_steps
        j = 0
        while i < len(trace.position) and j < self.BACKPROP_WINDOW_SIZE and state.current_step < self.environment.STEPS_PER_EPISODE:
            # activate network only if at least one action in the trace is non-zero
            if reduce(lambda x, y: x or y != 0, trace.actions[i], False):
                sensors = self.environment.compute_sensors(state)
                actions = self.network_action(sensors)

                # Don't run backprop on the first iteration, i.e. before the agent moves
                if i > self.passed_steps:
                    # calculate desired actions based on current state of agent and position in trace
                    # x-y actions
                    #poserr = [trace.position[i].x - state.position.x, trace.position[i].y - state.position.y]
                    #desired_actions = [poserr[0]/self.environment.VELOCITY, poserr[1]/self.environment.VELOCITY]

                    # r-theta actions
                    poserrx = trace.position[i].x - state.position.x
                    poserry = trace.position[i].y - state.position.y
                    errpos = sqrt(poserrx*poserrx + poserry*poserry)
                    errpos = errpos/self.environment.VELOCITY
                    errtheta = degrees(atan2(poserry, poserrx)) - state.rotation.z
                    errtheta = errtheta - floor(errtheta/360)*360  # range [0, 360)
                    if errtheta > 180: errtheta = errtheta - 360   # range [-180, 180]
                    errtheta = errtheta/(2*self.environment.ANGULAR_VELOCITY)
                    desired_actions = [errpos, errtheta]

                    #for j in range(len(desired_actions)):
                    #    if desired_actions[j] < -0.5: desired_actions[j] = -0.5
                    #    elif desired_actions[j] > 0.5: desired_actions[j] = 0.5

                    # calculate error based on desired action and network output
                    error = [desired_actions[0] - actions[0], desired_actions[1] - actions[1]]

                    self.net.load_errors(error)
                    self.net.backprop()

                # calculate new position, orientation, and velocity
                self.environment.perform_actions(state, actions)
                state.current_step += 1
                j += 1

            i += 1

        self.org.update_genotype()
