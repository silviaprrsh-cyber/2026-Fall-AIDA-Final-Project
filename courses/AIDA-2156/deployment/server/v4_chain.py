import torch
from torch import nn

# Fixed-arrival depth model: no timestamps, lag or target values in the input.
ROUTING_NODES = ('P01', 'P02', 'P03', 'P04', 'P05', '05CC002')
_ROUTING_STATIONS = ('dickson', 'little_red_deer', 'medicine')
ROUTING_FEATURES = tuple(f'{station}_q_m3_s' for station in _ROUTING_STATIONS) + tuple(
    f'{station}_rain_{hours}h_mm' for station in _ROUTING_STATIONS for hours in (1, 6, 24)
)


class RoutingDepthChain(nn.Module):
    """Six segment MLPs; prior segment depth is carried as a differentiable state."""

    def __init__(self, center, scale, distances=None):
        super().__init__()
        center = torch.as_tensor(center, dtype=torch.float32)
        scale = torch.as_tensor(scale, dtype=torch.float32)
        n_nodes, n_inputs = len(ROUTING_NODES), len(ROUTING_FEATURES)
        distances = (torch.ones(n_nodes, dtype=torch.float32)*10000 if distances is None
                     else torch.as_tensor(distances, dtype=torch.float32))
        if (center.shape != (n_inputs,) or scale.shape != (n_inputs,) or
                distances.shape != (n_nodes,) or not torch.isfinite(center).all() or
                not torch.isfinite(scale).all() or not torch.isfinite(distances).all() or
                (scale <= 0).any() or (distances < 0).any() or distances.sum() <= 0):
            raise ValueError('Invalid training normalization or six-segment geometry')
        self.register_buffer('center', center.detach().clone())
        self.register_buffer('scale', scale.detach().clone())
        self.register_buffer('distances', distances.detach().clone())
        self.register_buffer('chainages', torch.cumsum(distances, dim=0)/distances.sum())
        self.blocks = nn.ModuleList(
            nn.Sequential(nn.Linear(n_inputs + 3, 16), nn.Tanh(),
                          nn.Linear(16, 8), nn.Tanh(), nn.Linear(8, 1))
            for _ in ROUTING_NODES
        )
        for block in self.blocks:
            nn.init.normal_(block[-1].weight, std=0.03)
            nn.init.zeros_(block[-1].bias)

    def forward(self, features):
        if features.ndim != 2 or features.shape[1] != len(ROUTING_FEATURES):
            raise ValueError('Expected one row of twelve PostgreSQL features per arrival')
        z = ((torch.log1p(features)-self.center)/self.scale).clamp(-8, 8)
        # Softplus(0.54) is approximately 1 m: an initialization reference, not a label.
        state = torch.full_like(z[:, 0], 0.54)
        outputs = []
        for i, block in enumerate(self.blocks):
            previous_depth = torch.nn.functional.softplus(state)
            local = torch.stack((torch.log1p(previous_depth),
                                 torch.ones_like(state)*self.distances[i]/10000,
                                 torch.ones_like(state)*self.chainages[i]), dim=1)
            delta = block(torch.cat((z, local), dim=1)).squeeze(1)
            state = state + delta
            outputs.append(torch.nn.functional.softplus(state))
        return torch.stack(outputs, dim=1)
