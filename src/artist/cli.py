"""
Unified art CLI router - all art commands under 'vibegame art'.

Commands are registered directly (not as sub-groups) for flat access:
    vibegame art cut          -> cut.py
    vibegame art collate      -> cut.py
    vibegame art concat       -> compose.py
    vibegame art canvas       -> compose.py
    vibegame art edit         -> edit.py
    vibegame art animation    -> animation.py
    vibegame art f2v          -> animation.py
    vibegame art analyze      -> analyze.py
    vibegame art tree         -> analyze.py
    vibegame art label        -> label.py
    vibegame art rmbg         -> rmbg.py
    vibegame art perfectify   -> perfectify.py
    vibegame art pixel        -> pixel.py
    vibegame art v2f          -> video.py
    vibegame art decompose    -> decompose.py
    vibegame art gen image    -> imagegen.py
    vibegame art gen video    -> videogen.py
    vibegame art gen list     -> imagegen.py
"""

import typer

art_app = typer.Typer(
    name="art",
    help="Art toolkit - sprite processing, color analysis, and image editing",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)

# Register commands directly on art_app (flat, not nested sub-groups)
from .cut import cmd_cut, cmd_collate
from .compose import cmd_concat, cmd_canvas
from .edit import cmd_edit
from .animation import cmd_animation, cmd_f2v
from .analyze import cmd_analyze, cmd_tree
from .label import cmd_label
from .rmbg import cmd_rmbg
from .perfectify import cmd_perfectify
from .pixel import pixel_app
from .video import cmd_v2f
from .decompose import cmd_decompose
from .imagegen import cmd_image, cmd_list
from .videogen import cmd_video

art_app.command("cut")(cmd_cut)
art_app.command("collate")(cmd_collate)
art_app.command("concat")(cmd_concat)
art_app.command("canvas")(cmd_canvas)
art_app.command("edit")(cmd_edit)
art_app.command("animation")(cmd_animation)
art_app.command("f2v")(cmd_f2v)
art_app.command("analyze")(cmd_analyze)
art_app.command("tree")(cmd_tree)
art_app.command("label")(cmd_label)
art_app.command("rmbg")(cmd_rmbg)
art_app.command("perfectify")(cmd_perfectify)
art_app.add_typer(pixel_app, name="pixel")
art_app.command("v2f")(cmd_v2f)
art_app.command("decompose")(cmd_decompose)

# Generation sub-group
gen_app = typer.Typer(
    name="gen",
    help="AI asset generation (image / video)",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)
gen_app.command("image")(cmd_image)
gen_app.command("video")(cmd_video)
gen_app.command("list")(cmd_list)
art_app.add_typer(gen_app, name="gen")
