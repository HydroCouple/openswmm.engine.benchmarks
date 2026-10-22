"""Record identity for an existing completed clean-archive build."""
from __future__ import annotations
import json
from pathlib import Path
from .suite import binary_manifest
from .sources import digest


def record(source_manifest,destination):
    source_manifest=Path(source_manifest)
    data=json.loads(source_manifest.read_text(encoding='utf-8'))
    build=Path(data['build']);exe=build/'src/cli/openswmm'
    if not exe.exists():raise ValueError('Clean build CLI is absent')
    if (Path(data['source'])/'.git').exists():raise ValueError('Expected immutable clean git archive')
    cache={}
    for line in (build/'CMakeCache.txt').read_text(encoding='utf-8').splitlines():
        if '=' in line and ':' in line.split('=',1)[0] and not line.startswith(('#','//')):
            k,v=line.split('=',1);cache[k.split(':',1)[0]]=v
    data.update(executable=str(exe),binaries=binary_manifest(exe),cmake_cache_sha256=digest((build/'CMakeCache.txt').read_bytes()),
                compiler=cache.get('CMAKE_CXX_COMPILER','unknown'),build_type=cache.get('CMAKE_BUILD_TYPE','unknown'),release_flags=cache.get('CMAKE_CXX_FLAGS_RELEASE','unknown'),backend='CPU',
                features={'2d':True,'2d_hdf5_output':True,'gpu_plugin':False,'geopackage':False,'model_hdf5_io':False},
                input_source_manifest_sha256=digest(source_manifest.read_bytes()))
    Path(destination).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    return data

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source_manifest',type=Path);ap.add_argument('destination',type=Path)
    args=ap.parse_args();print(record(args.source_manifest,args.destination)['executable'])
