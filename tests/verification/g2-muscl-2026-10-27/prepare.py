"""Build isolated diagnostic controls from recorded committed source only."""
from pathlib import Path
import difflib
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
ENGINE = ROOT.parent / 'openswmm.engine'
OUT = ROOT / 'results/uk_2d/g2-muscl-2026-10-27'
WORK = ENGINE / 'tests/verification/g2_muscl_2026-10-27'
SOURCE = WORK / 'source'
BASE = '50e146750bc723dfeacdb903909d49465f8031b0'
CORRECTED = '336ca72982fca99305586f05113b43c6ed1600b8'
REL = 'src/engine/2d/solver/ExplicitInertialSolver.cpp'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    with (WORK / log).open('w', encoding='utf-8') as stream:
        subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, check=True)


def prepare_source():
    assert not SOURCE.exists()
    SOURCE.mkdir(parents=True)
    OUT.mkdir(exist_ok=True)
    raw = subprocess.check_output(['git', '-C', str(ENGINE), 'archive', BASE])
    (OUT / 'base-source.tar').write_bytes(raw)
    with tarfile.open(fileobj=io.BytesIO(raw), encoding='utf-8') as archive:
        archive.extractall(SOURCE, filter='data')
    for rel in [REL, REL.replace('.cpp', '.hpp'), 'tests/unit/engine/test_2d_swe_reconstruction.cpp',
                'tests/unit/engine/data/swe_reconstruction/bank_corner.mesh',
                'tests/unit/engine/data/swe_reconstruction/bank_corner.json']:
        target = SOURCE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(['git', '-C', str(ENGINE), 'show', CORRECTED + ':' + rel]))
    original = (SOURCE / REL).read_text(encoding='utf-8')
    assert sha(SOURCE / REL) == 'c8124296eb21b358590493aa016ebccd4cafd2d3abdff38e522e169db88a9271'
    text = original
    anchor = 'void ExplicitInertialSolver::computeLimitedGradientsSwe() {\n'
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + '''    // Isolated diagnostics only: no production option or default change.
    static const std::string experiment = [] {
        const char* value = std::getenv("OPENSWMM_G2_RECONSTRUCTION");
        const std::string mode = value ? value : "baseline";
        if (mode != "baseline" && mode != "surface-only" && mode != "velocity-only" &&
            mode != "common-velocity" && mode != "common-all")
            throw std::invalid_argument("Unknown isolated G2 reconstruction experiment.");
        return mode;
    }();
''')
    anchor = '        gex_[i] = phi[0] * gx[0];'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        if (experiment == "common-velocity")
            phi[1] = phi[2] = std::min(phi[1], phi[2]);
        if (experiment == "common-all") {
            const double common = std::min({phi[0], phi[1], phi[2], phi[3]});
            for (double& value : phi)
                value = common;
        }
        if (experiment == "surface-only")
            phi[1] = phi[2] = 0;
        if (experiment == "velocity-only")
            phi[0] = phi[3] = 0;
''' + anchor)
    (SOURCE / REL).write_text(text, encoding='utf-8')
    (OUT / 'diagnostic.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                                                   fromfile='a/' + REL, tofile='b/' + REL)), encoding='utf-8')
    design = dict(base_revision=BASE, corrected_revision=CORRECTED,
                  original_solver_sha256=hashlib.sha256(original.encode()).hexdigest(),
                  experimental_solver_sha256=sha(SOURCE / REL), source_archive_sha256=sha(OUT / 'base-source.tar'),
                  controls=['baseline', 'surface-only', 'velocity-only', 'common-velocity', 'common-all'],
                  qualification='All native and analytical outcomes retained. Common-factor candidates require all 12 native and 16 analytical checks. Deliberate slope-removal controls are diagnostic only; any safety or analytical failure excludes their Test 6 run.',
                  scope='Changes limited to final scalar/velocity slope factors, used by both interior and reflective wall faces. No physical coefficient changes.')
    (OUT / 'experiment-design.json').write_text(json.dumps(design, indent=2) + '\n', encoding='utf-8')


def build():
    design = json.loads((OUT / 'experiment-design.json').read_text(encoding='utf-8'))
    assert sha(SOURCE / REL) == design['experimental_solver_sha256']
    command(['cmake', '-S', str(SOURCE), '-B', str(WORK / 'build'), '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=Release', '-DOPENSWMM_BUILD_2D=ON', '-DOPENSWMM_BUILD_PYTHON=OFF',
             '-DOPENSWMM_BUILD_TESTS=OFF', '-DOPENSWMM_BUILD_UNIT_TESTS=OFF',
             '-DOPENSWMM_BUILD_GPU_PLUGIN=OFF',
             '-Dhdf5_DIR=' + str(ROOT.parent / 'openswmm.gui/build/vcpkg_installed/arm64-osx/share/hdf5')], 'configure.log')
    command(['cmake', '--build', str(WORK / 'build'), '--target', 'openswmm', '-j', '4'], 'build.log')
    pin = OUT / 'pinned-experiments'
    (pin / 'bin').mkdir(parents=True)
    (pin / 'engine').mkdir()
    shutil.copy2(WORK / 'build/bin/Release/openswmm', pin / 'bin/openswmm')
    shutil.copy2(WORK / 'build/src/engine/libopenswmm.engine.6.0.0.dylib', pin / 'engine/libopenswmm.engine.6.0.0.dylib')
    (pin / 'engine/libopenswmm.engine.dylib').symlink_to('libopenswmm.engine.6.0.0.dylib')
    (pin / 'engine/libopenswmm.engine.6.dylib').symlink_to('libopenswmm.engine.6.0.0.dylib')
    native = WORK / 'native-source'
    native.mkdir()
    (native / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.21)
project(g2_muscl_native LANGUAGES CXX)
find_package(GTest CONFIG REQUIRED)
foreach(pair IN ITEMS "reconstruction|test_2d_swe_reconstruction.cpp" "cpu|test_2d_cpu_correctness.cpp")
 string(REPLACE "|" ";" parts ${pair})
 list(GET parts 0 name)
 list(GET parts 1 file)
 add_executable(${name} ${ENGINE_SOURCE}/tests/unit/engine/${file})
 target_compile_features(${name} PRIVATE cxx_std_20)
 target_include_directories(${name} PRIVATE ${ENGINE_SOURCE}/src/engine ${ENGINE_SOURCE}/include)
 target_link_libraries(${name} PRIVATE GTest::gtest_main ${ENGINE_LIBRARY})
endforeach()
''', encoding='utf-8')
    command(['cmake', '-S', str(native), '-B', str(WORK / 'native'), '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             '-DENGINE_SOURCE=' + str(SOURCE), '-DENGINE_LIBRARY=' + str(pin / 'engine/libopenswmm.engine.6.0.0.dylib')], 'native-configure.log')
    command(['cmake', '--build', str(WORK / 'native'), '-j', '2'], 'native-build.log')
    design['binary_sha256'] = {str(p.relative_to(OUT)): sha(p) for p in [pin / 'bin/openswmm', pin / 'engine/libopenswmm.engine.6.0.0.dylib']}
    (OUT / 'experiment-design.json').write_text(json.dumps(design, indent=2) + '\n', encoding='utf-8')
    print('Isolated diagnostic build complete', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-build', action='store_true')
    args = parser.parse_args()
    if not args.resume_build:
        prepare_source()
    build()
