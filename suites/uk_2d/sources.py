"""Checksum-locked reads; archive member names are never extracted to disk."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATIONS = Path(__file__).with_name('specifications')
INVENTORY = SPECIFICATIONS/'source-inventory.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Sources:
    def __init__(self, archive, inventory=INVENTORY):
        self.records = {r['path']: r for r in json.loads(Path(inventory).read_text(encoding='utf-8'))['files']}
        self.name = 'Benchmarking_Model_Data.zip'
        data = Path(archive).read_bytes()
        self.check(self.name, data)
        self.outer = zipfile.ZipFile(io.BytesIO(data))
        self.archives = {}
        self.used = {}

    def check(self, key, data):
        record = self.records.get(key)
        if record is None or digest(data) != record['sha256'] or len(data) != record['bytes']:
            raise ValueError(f'Unrecognized or altered source: {key}')

    def read(self, test, basename):
        nested = f'Test{test}_dataset_2010.zip'
        if nested not in self.archives:
            data = self.outer.read(nested)
            self.check(self.name+'!/'+nested, data)
            self.archives[nested] = zipfile.ZipFile(io.BytesIO(data))
        archive = self.archives[nested]
        names = [n for n in archive.namelist() if PurePosixPath(n).name.lower() == basename.lower()]
        if len(names) != 1:
            raise ValueError(f'Expected exactly one {basename}, got {names}')
        name = names[0]
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or PureWindowsPath(name).drive or '\\' in name:
            raise ValueError('Unsafe archive member name')
        key = self.name+'!/'+nested+'!/'+name
        data = archive.read(name)
        self.check(key, data)
        self.used[key] = self.records[key]
        return data

    def probes(self, test, basename):
        rows = list(csv.reader(io.StringIO(self.read(test, basename).decode('utf-8-sig'))))
        result = [{'id': r[0], 'x': float(r[1]), 'y': float(r[2])} for r in rows[1:] if r]
        if len({p['id'] for p in result}) != len(result):
            raise ValueError('Duplicate probes')
        return result

    def forcing(self, test, basename):
        rows = list(csv.reader(io.StringIO(self.read(test, basename).decode('utf-8-sig'))))
        unit = rows[0][0].lower()
        if 'min' in unit:
            factor = 60
        elif '(s)' in unit:
            factor = 1
        else:
            raise ValueError('Unrecognized forcing time units')
        data = np.asarray([[float(r[0])*factor, float(r[1])] for r in rows[1:] if r])
        if not np.isfinite(data).all() or np.any(np.diff(data[:, 0]) <= 0) or data[0, 0] != 0:
            raise ValueError('Invalid forcing times/values')
        return data


class Raster:
    def __init__(self, data):
        text = data.decode('ascii')
        lines = text.splitlines()
        head = dict(line.lower().split() for line in lines[:6])
        self.nx, self.ny = int(head['ncols']), int(head['nrows'])
        self.dx = float(head['cellsize'])
        self.x0 = float(head['xllcorner']) + self.dx/2
        self.y0 = float(head['yllcorner']) + self.dx/2
        self.z = np.loadtxt(io.StringIO('\n'.join(lines[6:])))[::-1]
        if self.z.shape != (self.ny, self.nx):
            raise ValueError('Raster dimensions disagree with header')
        self.z[self.z == float(head['nodata_value'])] = np.nan

    def sample(self, x, y, allow_nodata=False):
        """Bilinear interpolation between pixel centers; no extrapolation."""
        fx = (np.asarray(x)-self.x0)/self.dx
        fy = (np.asarray(y)-self.y0)/self.dx
        if np.any((fx < 0) | (fx > self.nx-1) | (fy < 0) | (fy > self.ny-1)):
            raise ValueError('Sampling outside raster support')
        ix = np.minimum(np.floor(fx).astype(int), self.nx-2)
        iy = np.minimum(np.floor(fy).astype(int), self.ny-2)
        tx, ty = fx-ix, fy-iy
        result = ((1-tx)*(1-ty)*self.z[iy,ix] + tx*(1-ty)*self.z[iy,ix+1]
                  + (1-tx)*ty*self.z[iy+1,ix] + tx*ty*self.z[iy+1,ix+1])
        if not allow_nodata and not np.isfinite(result).all():
            raise ValueError('NODATA intersects mesh')
        return result


def integral(data):
    return float(np.sum(np.diff(data[:,0])*(data[:-1,1]+data[1:,1])/2))
