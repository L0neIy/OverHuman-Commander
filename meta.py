import pandas as pd

class MetaLearner:
    def __init__(self, cfg=None, expert_names=None):
        self.cfg = cfg
        self.expert_names = expert_names or []
        self.history = pd.DataFrame(columns=self.expert_names)
        self.weights = {name: 1.0 for name in self.expert_names}

        # ใช้ getattr แทน .get()
        self.decay = getattr(self.cfg, 'decay', 0.9)


    def get_weight(self, expert_name):
        return self.weights.get(expert_name, 1.0)

    def update(self, signals, realized_pnl):
        for name, (direction, strength, reason) in signals.items():
            if name not in self.weights:
                continue
            contrib = direction * strength
            if name not in self.history.columns:
                self.history[name] = []
            if len(self.history) == 0:
                self.history.loc[0, name] = contrib * realized_pnl
            else:
                last = self.history[name].iloc[-1] if not self.history[name].empty else 0
                new_val = self.decay * last + (1 - self.decay) * contrib * realized_pnl
                self.history.loc[len(self.history), name] = new_val
            perf = self.history[name].iloc[-1]
            w = max(0.0, min(2.0, 1.0 + perf))
            self.weights[name] = w

    def normalize_weights(self):
        total = sum(self.weights.values()) or 1.0
        for k in self.weights:
            self.weights[k] /= total
