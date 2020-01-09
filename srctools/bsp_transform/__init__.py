"""Transformations that can be applied to the BSP file."""
from pathlib import Path
from typing import Callable, Dict, Tuple, List

from srctools import FileSystem, VMF, Output, Entity
from srctools.logger import get_logger
from srctools.packlist import PackList
from srctools.game import Game


LOGGER = get_logger(__name__, 'bsp_trans')

__all__ = ['Context', 'trans', 'run_transformations']


class Context:
    """Bundles information useful for each transformation.

    This allows them to ignore data they don't use.
    """
    def __init__(
        self, 
        filesys: FileSystem,
        vmf: VMF,
        pack: PackList,
        bsp_path: str,
        game: Game,
    ) -> None:
        self.sys = filesys
        self.vmf = vmf
        self.pack = pack
        self.bsp_path = Path(bsp_path)
        self.game = game

        self._io_remaps = {}  # type: Dict[Tuple[str, str], List[Output]]
        self._ent_code = {}  # type: Dict[Entity, str]

    def add_io_remap(self, name: str, *outputs: Output) -> None:
        """Register an output to be replaced.

        This is used to convert inputs to comp_ entities into their real
        forms. The output name in the output is the input that will be replaced.
        """
        name = name.casefold()
        for out in outputs:
            inp_name = out.output.casefold()
            out.output = ''
            self._io_remaps[name, inp_name].append(out)

    def add_code(self, ent: Entity, code: str) -> None:
        """Register VScript code to be run on spawn for this entity.

        This way multiple such options can be merged together.
        """
        try:
            existing = self._ent_code[ent]
        except KeyError:
            self._ent_code[ent] = code
        else:
            self._ent_code[ent] = '{}\n{}'.format(existing, code)


TransFunc = Callable[[Context], None]
TRANSFORMS = {}  # type: Dict[str, TransFunc]


def trans(name: str) -> Callable[[TransFunc], TransFunc]:
    """Add a transformation procedure to the list."""
    def deco(func: TransFunc) -> TransFunc:
        """Stores the transformation."""
        TRANSFORMS[name] = func
        return func
    return deco


# noinspection PyProtectedMember
def run_transformations(
    vmf: VMF,
    filesys: FileSystem,
    pack: PackList,
    bsp_path: str,
    game: Game,
) -> None:
    """Run all transformations."""
    context = Context(filesys, vmf, pack, bsp_path, game)

    for func_name, func in TRANSFORMS.items():
        LOGGER.info('Running "{}"...', func_name)
        func(context)

    if context._ent_code:
        LOGGER.info('Injecting VScript code...')
        for ent, code in context._ent_code.items():
            init_scripts = ent['vscripts'].split()
            path = pack.inject_vscript(code.replace('`', '"'))
            # Don't include scripts/vscripts/ in the value, that's assumed.
            init_scripts.append(path[17:])
            ent['vscripts'] = ' '.join(init_scripts)

    if context._io_remaps:
        LOGGER.info('Remapping outputs...')
        for ent in vmf.entities:
            for out in ent.outputs[:]:
                try:
                    remaps = context._io_remaps[
                        out.target.casefold(),
                        out.input.casefold(),
                    ]
                except KeyError:
                    continue
                ent.outputs.remove(out)
                for new_out in remaps:
                    ent.outputs.append(Output(
                        out.output,
                        new_out.target,
                        new_out.input,
                        new_out.params or out.params,
                        out.delay + new_out.delay,
                        times=min(new_out.only_once, out.only_once),
                    ))


def _load() -> None:
    """Import all submodules.

    This loads the transformations.
    """
    from srctools.bsp_transform import (
        antline,
        brush_ents,
        entfinder,
        globals,
        instancing,
        kv_setter,
        movement,
        packing,
        portal2,
        sceneset,
        scriptvar_setter,
    )
_load()
