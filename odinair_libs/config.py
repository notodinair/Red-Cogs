from typing import Sequence, Dict, Optional, Tuple

from collections import namedtuple
from redbot.core.bot import Red
from redbot.core.config import Value, Group, Config

__all__ = ["toggle", "group_toggle", "fix_config_fuckup"]


async def fix_config_fuckup(config: Config, identifier: int, bot: Red):
    """Fix a Config fuckup involving `type` being used for cog identifiers

    This issue affects `Logs`, `Starboard`, and any other cogs that may instantiate a Config object
    with a non-instantiated cog class in the `cog_instance` argument when calling `get_conf`

    It'd probably be important to note that this does not seem to be the result of a bug
    in the Red core, but instead an unintended consequence resulting from how the above cogs
    created their Config objects.

    **This has not been extensively tested**, and as such it could be completely broken,
    and I wouldn't have a damn clue.
    """
    fuckedup_config = Config.get_conf(None, identifier=identifier, cog_name="type")

    fuckedup_globals = await fuckedup_config.all()
    fixed_globals = await config.all()
    if not fixed_globals:
        for item in fuckedup_globals:
            await config.set_raw(item, fuckedup_globals[item])

    Guild = namedtuple("Guild", "id")
    Member = namedtuple("Member", "id guild")

    fuckedup_guilds = await fuckedup_config.all_guilds()
    fuckedup_members = await fuckedup_config.all_members()
    fixed_guilds = await config.all_guilds()
    fixed_members = await config.all_members()
    for gid in fuckedup_guilds:  # fix guilds & members
        if gid in fixed_guilds:
            continue
        guild = Guild(id=gid)
        await config.guild(guild).set(fuckedup_guilds[gid])
        for mid in fuckedup_members[gid]:  # fix members
            if mid in fixed_members.get(gid, {}):
                continue
            member = Member(id=mid, guild=guild)
            await config.member(member).set(fuckedup_members[gid][mid])

    fuckedup_channels = await fuckedup_config.all_channels()
    fixed_channels = await config.all_channels()
    for cid in fuckedup_channels:
        if cid in fixed_channels:
            continue
        channel = bot.get_channel(cid)
        if channel is None:
            continue
        await config.channel(channel).set(fuckedup_channels[cid])


def _parse_bool(val: str) -> Optional[bool]:
    if val in ("yes", "y", "on", "true"):
        return True
    elif val in ("no", "n", "off", "false"):
        return False
    return None


def _parse_setting_param(param: str) -> Tuple[str, Optional[bool]]:
    param = param.split("=")
    if len(param) == 1:
        return param[0], None
    return param[0], _parse_bool(param[1])


async def toggle(value: Value) -> bool:
    """Toggle a config bool

    Parameters
    ----------
    value: Value
        A Config ``Value`` object that is expected to return a bool-like value

    Returns
    --------
    bool
        The new value
    """
    current = not await value()
    await value.set(current)
    return current


async def group_toggle(group: Group, toggle_keys: Sequence[str], *, defaults: Dict[str, bool] = None,
                       slots: Sequence[str] = None, strict_slots: bool = False) -> Dict[str, bool]:
    """Group config toggle

    Parameters
    -----------
    group: Group
        The Config ``Group`` to edit
    toggle_keys: Sequence[str]
        The keys in the ``Group`` to edit. These can be formatted similarly to `value=true` or `value=no` to specify
        a specific bool value
    defaults: Dict[str, bool]
        The ``Group`` defaults. Defaults to `group.defaults`
    slots: Sequence[str]
        The available keys in the ``Group`` to allow modification of. Defaults to the values of ``toggle_keys``,
        effectively implying that any key is allowed.
    strict_slots: bool
        Whether or not a KeyError is raised if any keys passed in ``toggle_keys`` are not in ``slots``.
        If this is False, any items not in ``slots`` are silently ignored instead.

    Returns
    --------
    Dict[str, bool]
        The modified ``Group`` settings

    Raises
    -------
    RuntimeError
        Raised if the given ``Group`` does not return a dict value
    KeyError
        Raised if ``strict_slots`` is True and an item in ``toggle_keys`` does not exist in ``slots``
    """
    if defaults is None:
        defaults = group.defaults
    if slots is None:
        slots = [x.split("=")[0] for x in toggle_keys]
    toggle_keys = [x for x in toggle_keys if x.split("=")[0] in slots]
    toggles = {}
    for item in toggle_keys:
        item = _parse_setting_param(item)
        if item[0] not in slots and strict_slots is True:
            raise KeyError(item[0])
        toggles[item[0]] = item[1]
    async with group() as settings:
        if not isinstance(settings, dict):
            raise RuntimeError("group did not return a dict")
        for key in defaults:
            val = defaults.get(key, False)
            if key not in settings:
                settings[key] = val
        for key in toggles:
            val = toggles.get(key, None)
            if val is None:
                val = not settings.get(key, False)
            settings[key] = val
        return {**defaults, **settings}
