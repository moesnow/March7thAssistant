from tasks.power.power import Power
from tasks.power.instance import Instance
from .doubleactivity import DoubleActivity


class GardenOfPlenty(DoubleActivity):
    def __init__(self, name, enabled, instance_type, instance_names, instance_names_challenge_count):
        super().__init__(name, enabled)
        self.instance_type = instance_type
        self.instance_names = instance_names
        self.challenges_count = instance_names_challenge_count

    def _run_instances(self, reward_count):
        instance_type = self.instance_type
        instance_name = self.instance_names[instance_type]
        challenge_count = self.challenges_count[instance_type]
        instance_power_min = 10
        if (challenge_count >= 1 and challenge_count <= 6):
            instance_power_max = challenge_count * 10
        else:
            instance_power_max = 60

        power = min(Power.get(), reward_count * instance_power_min)

        full_runs = power // instance_power_max
        if full_runs:
            result = Instance.run(instance_type, instance_name, instance_power_max, full_runs)
            if result == "Failed":
                return False

        partial_run_power = power % instance_power_max
        if partial_run_power >= instance_power_min:
            result = Instance.run(instance_type, instance_name, partial_run_power, 1)
            if result == "Failed":
                return False

        return True
