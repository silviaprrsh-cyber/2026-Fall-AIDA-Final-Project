"""Six jointly trained weather-aware MLP blocks with differentiable section areas."""
import numpy as np
import torch
from torch import nn
import hashlib
import json
from pathlib import Path


class WeatherChain(nn.Module):
    def __init__(self, depths, areas, distances, center, scale, hidden=16):
        super().__init__()
        self.register_buffer('depths', torch.as_tensor(depths, dtype=torch.float32))
        self.register_buffer('areas', torch.as_tensor(areas, dtype=torch.float32))
        self.register_buffer('distances', torch.as_tensor(distances, dtype=torch.float32))
        self.register_buffer('center', torch.as_tensor(center, dtype=torch.float32))
        self.register_buffer('scale', torch.as_tensor(scale, dtype=torch.float32))
        self.blocks = nn.ModuleList([
            nn.Sequential(nn.Linear(15, hidden), nn.Tanh(), nn.Linear(hidden, 8),
                          nn.Tanh(), nn.Linear(8, 2)) for _ in range(6)])
        for block in self.blocks:
            nn.init.zeros_(block[-1].weight)
            nn.init.zeros_(block[-1].bias)

    def area(self, i, h):
        grid, values = self.depths[i], self.areas[i]
        h = torch.clamp(h, min=grid[0], max=grid[-1])
        j = torch.searchsorted(grid, h.contiguous()).clamp(1, len(grid)-1)
        fraction = (h-grid[j-1])/(grid[j]-grid[j-1])
        return values[j-1] + fraction*(values[j]-values[j-1])

    def forward(self, initial, context):
        q, h, velocity, elapsed = initial.unbind(1)
        z = torch.clamp((context-self.center)/self.scale, -8, 8)
        states, corrections = [], []
        for i, block in enumerate(self.blocks):
            if i:
                elapsed = elapsed + self.distances[i]/velocity.clamp_min(1e-5)
            lo, hi = self.depths[i, 0], self.depths[i, -1]
            incoming_area = self.area(i, h)
            local_context = z.clone()
            if i != 0:
                local_context[:, :4] = 0
            if i != 3:
                local_context[:, 8] = 0
            state = torch.stack([torch.log1p(q)/5, torch.log1p(h), velocity/5,
                                 torch.ones_like(q)*self.distances[i]/10000,
                                 incoming_area/1000, torch.ones_like(q)*hi/10], 1)
            delta = torch.tanh(block(torch.cat([state, local_context], 1)))
            q = q*torch.exp(.35*delta[:, 0])
            ratio = ((h-lo)/(hi-lo)).clamp(.001, .999)
            h = lo+(hi-lo)*torch.sigmoid(torch.logit(ratio)+delta[:, 1])
            area = self.area(i, h)
            velocity = q/area.clamp_min(1e-6)
            states.append(torch.stack([q,h,area,velocity,elapsed],1))
            corrections.append(delta)
        return torch.stack(states,1), torch.stack(corrections,1)


def nearest_labels(origins, delay, times, values, lower, upper, max_transit=604800, tolerance=1800):
    """Discrete label assignment is detached; ties choose the earlier observation."""
    arrival = np.asarray(origins,dtype=np.float64)+np.asarray(delay,dtype=np.float64)
    index = np.searchsorted(times, arrival)
    left = np.clip(index-1,0,len(times)-1)
    right = np.clip(index,0,len(times)-1)
    chosen = np.where(np.abs(times[left]-arrival)<=np.abs(times[right]-arrival),left,right)
    stamps = times[chosen]
    valid = (np.isfinite(arrival) & (delay>=0) & (delay<=max_transit) &
             (np.abs(stamps-arrival)<=tolerance) & (stamps>=lower) & (stamps<upper) &
             (stamps>=origins))
    return values[chosen], valid, stamps, stamps-arrival


def error_metrics(predictions, labels, valid):
    result={'origins':len(valid),'matched':int(valid.sum()),'coverage':float(valid.mean())}
    for i,name in enumerate(['discharge','variable_depth']):
        e=predictions[valid,i]-labels[valid,i]
        result[name]={'bias':float(e.mean()) if len(e) else None,
                      'mae':float(np.abs(e).mean()) if len(e) else None,
                      'rmse':float(np.sqrt(np.mean(e*e))) if len(e) else None}
    return result


def load_trained(folder):
    """Load local tensor-only weights after checking the recorded artifact identity."""
    folder=Path(folder)
    report=json.loads((folder/'training_report.json').read_text())
    path=folder/'model.pt'
    if report['model_type']!='six_segment_weather_mlp_joint_endpoint':
        raise ValueError('Unsupported neural model type')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=report['saved_model_sha256']:
        raise ValueError('Neural model checksum mismatch')
    state=torch.load(path,map_location='cpu',weights_only=True)
    model=WeatherChain(state['depths'],state['areas'],state['distances'],state['center'],state['scale'])
    model.load_state_dict(state,strict=True)
    model.eval()
    return model,report


def checks():
    torch.manual_seed(42)
    grid=np.tile(np.geomspace(.01,5,128),(6,1))
    model=WeatherChain(grid,10*grid,[0,100,100,100,100,100],np.zeros(9),np.ones(9))
    initial=torch.tensor([[20.,1.,2.,100.],[25.,1.2,2.,100.]])
    context=torch.ones(2,9)
    states,_=model(initial,context)
    assert torch.allclose(states[:,:,3],states[:,:,0]/states[:,:,2])
    assert torch.all(states[:,1:,4]>states[:,:-1,4])
    loss=states[:,-1,:2].square().mean()
    loss.backward()
    assert all(block[-1].weight.grad.abs().sum()>0 for block in model.blocks)
    with torch.no_grad():
        for block in model.blocks:
            block[-1].weight.normal_(0,.03)
    changed=model(initial,context*2)[0]
    assert not torch.allclose(changed,model(initial,context)[0])
    labels,valid,stamps,_=nearest_labels(np.array([100.,100.]),np.array([50.,500.]),
        np.array([140.,160.]),np.array([[1.,2.],[3.,4.]]),100,200,tolerance=20)
    assert stamps[0]==140 and valid.tolist()==[True,False]
    assert np.array_equal(labels[0],[1,2])
    print('Neural checks passed: gradients in all six blocks, weather sensitivity, Q/A, time order, nearest ties and bounds.',flush=True)


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
