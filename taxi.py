#!/usr/bin/env python

class Taxi(object):

    def __init__(self, name=None, pool_name=None, time_limit=None, node_limit=None):
        self.name = name
        self.pool_name = pool_name
        self.time_limit = time_limit
        self.node_limit = node_limit
        self.time_last_submitted = None
        self.start_time = None  ## Not currently saved to DB, but maybe it should be?
        self.status = 'I'

    def __eq__(self, other):
        eq = (self.name == other.name)
        eq = eq and (self.pool_name == other.pool_name)
        eq = eq and (self.time_limit == other.time_limit)
        eq = eq and (self.node_limit == other.node_limit)
        eq = eq and (self.time_last_submitted == other.time_last_submitted)
        eq = eq and (self.start_time == other.start_time)
        eq = eq and (self.status == other.status)

        return eq

    def taxi_name(self):
        return '{0:s}_{1:d}'.format(self.pool_name, self.name)

    def rebuild_from_dict(self, taxi_dict):
        try:
            self.name = taxi_dict['name']
            self.pool_name = taxi_dict['pool_name']
            self.time_limit = taxi_dict['time_limit']
            self.node_limit = taxi_dict['node_limit']
            self.time_last_submitted = taxi_dict['time_last_submitted']
            self.status = taxi_dict['status']
        except KeyError:
            print "Error: attempted to rebuild taxi from malformed dictionary:"
            print taxi_dict
            raise
        except TypeError:
            print "Error: type mismatch in rebuilding taxi from dict:"
            print taxi_dict
            raise

    def __repr__(self):
        return "Taxi<{},{},{},{},{},'{}'>".format(self.name, self.pool_name, self.time_limit,
            self.node_limit, self.time_last_submitted, self.status)


    def execute_task(self, task):
        """Execute the given task, according to task['task_type']."""
        
        # Record start time
        pass

        # Run task
        task_type = task['task_type']
        if (task_type == 'die'):
            # Die
            pass
        elif (task_type == 'copy'):
            # Copy
            pass
        elif (task_type == 'run_script'):
            # Run script
            pass
        else:
            raise ValueError("Invalid task type specified: {}".format(task_type))

        # Return when complete
        return

    