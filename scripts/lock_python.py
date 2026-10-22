"""Generate the installed dependency closure, including requested extras."""
from importlib.metadata import distribution
from packaging.requirements import Requirement
from pathlib import Path
root=Path(__file__).resolve().parents[1]
queue=[Requirement(x) for x in (root/'backend/requirements.in').read_text().splitlines() if x and not x.startswith('#')]
visited=set();versions={}
while queue:
 r=queue.pop();d=distribution(r.name);key=(d.metadata['Name'].lower(),tuple(sorted(r.extras)))
 if key in visited:continue
 visited.add(key);versions[d.metadata['Name']]=d.version
 for text in d.requires or []:
  dep=Requirement(text)
  if dep.marker is None or any(dep.marker.evaluate({'extra':extra}) for extra in (r.extras or {''})):queue.append(dep)
(root/'backend/requirements.lock').write_text('\n'.join(f'{k}=={v}' for k,v in sorted(versions.items(),key=lambda x:x[0].lower()))+'\n')
print('Locked',len(versions),'packages')
