from tasks.power.power import Power
from tasks.power.instance import Instance
from .doubleactivity import DoubleActivity


class RealmOfTheStrange(DoubleActivity):
    def __init__(self, name, enabled, instance_names):
        super().__init__(name, enabled)
        self.instance_names = instance_names

    def _run_instances(self, reward_count):
        instance_type = "侵蚀隧洞"
        instance_name = self.instance_names[instance_type]
        instance_power = 40

        power = min(Power.get(), reward_count * instance_power)

        full_runs = power // instance_power
        if full_runs:
            Instance.run(instance_type, instance_name, instance_power, full_runs)

        return True
