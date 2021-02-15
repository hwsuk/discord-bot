import asyncio
import contextlib
import functools
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union

import discord
from discord.ext import commands

_ReactableEmoji = Union[str, discord.Emoji]


async def menu(
    ctx: commands.Context,
    pages: Union[List[str], List[discord.Embed]],
    controls: dict,
    message: discord.Message = None,
    page: int = 0,
    timeout: float = 120.0,
    payload: Any = None,
):
    """
    An emoji-based menu

    All pages should be of the same type

    All functions for handling what a particular emoji does
    should be coroutines (i.e. :code:`async def`). Additionally,
    they must take all of the parameters of this function, in
    addition to a string representing the emoji reacted with.
    This parameter should be the last one, and none of the
    parameters in the handling functions are optional apart from payload.

    Parameters
    ----------
    ctx: commands.Context
        The command context
    pages: `list` of `str` or `discord.Embed`
        The pages of the menu.
    controls: dict
        A mapping of emoji to the function which handles the action for the
        emoji.
    message: discord.Message
        The message representing the menu. Usually None when first opening
        the menu
    page: int
        The current page number of the menu
    timeout: float
        The time (in seconds) to wait for a reaction
    payload: Any
        This can be of any type and is intended as a placeholder
        for anything you may want to pass down the menu in order to maintain state

    Raises
    ------
    RuntimeError
        If either of the notes above are violated
    """
    # Check that pages are of same type
    if not isinstance(pages[0], (discord.Embed, str)):
        raise RuntimeError("Pages must be of type discord.Embed or str")
    if not all(isinstance(x, discord.Embed) for x in pages) and not all(isinstance(x, str) for x in pages):
        raise RuntimeError("All pages must be of the same type")
    # Check that passed functions are asynchronous
    for key, value in controls.items():
        maybe_coro = value
        if isinstance(value, functools.partial):
            maybe_coro = value.func
        if not asyncio.iscoroutinefunction(maybe_coro):
            raise RuntimeError("Function must be a coroutine")
    current_page = pages[page]
    # Send message if it does not exist
    if not message:
        if isinstance(current_page, discord.Embed):
            message = await ctx.send(embed=current_page)
        else:
            message = await ctx.send(current_page)
        if len(pages) == 1:
            return
        # Don't wait for reactions to be added
        start_adding_reactions(message, controls.keys())
    else:
        try:
            if isinstance(current_page, discord.Embed):
                await message.edit(embed=current_page)
            else:
                await message.edit(content=current_page)
        except discord.NotFound:
            return
    # Wait for reactions
    try:
        react, _ = await ctx.bot.wait_for(
            "reaction_add",
            check=with_emojis(tuple(controls.keys()), message, ctx.author),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        if not ctx.me:
            return
        try:
            if message.channel.permissions_for(ctx.me).manage_messages:
                await message.clear_reactions()
            else:
                raise RuntimeError
        except (discord.Forbidden, RuntimeError):  # Cancel if cannot manage messages
            for key in controls.keys():
                try:
                    await message.remove_reaction(key, ctx.bot.user)
                except discord.Forbidden:
                    return
                except discord.HTTPException:
                    pass
        except discord.NotFound:
            return
    else:
        return await controls[str(react.emoji)](
            ctx=ctx,
            pages=pages,
            controls=controls,
            message=message,
            page=page,
            timeout=timeout,
            emoji=react.emoji,
            payload=payload,
        )


def start_adding_reactions(message: discord.Message, emojis: Iterable[_ReactableEmoji]) -> asyncio.Task:
    """
    Start adding reactions to a message.

    This is a non-blocking operation - calling this will schedule the
    reactions being added, but the calling code will continue to
    execute asynchronously. There is no need to await this function.

    Parameters
    ----------
    message: discord.Message
        The message to add reactions to.
    emojis : Iterable[Union[str, discord.Emoji]]
        The emojis to react to the message with.

    Returns
    -------
    asyncio.Task
        The task for the coroutine adding the reactions.
    """

    async def task():
        # The task should exit silently if the message is deleted
        with contextlib.suppress(discord.NotFound):
            for emoji in emojis:
                await message.add_reaction(emoji)

    return asyncio.create_task(task())


async def next_page(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
    payload: Any = None,
):
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    if page == len(pages) - 1:
        page = 0  # Loop around to the first item
    else:
        page += 1
    return await menu(
        ctx=ctx,
        pages=pages,
        controls=controls,
        message=message,
        page=page,
        timeout=timeout,
        payload=payload,
    )


async def prev_page(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
    payload: Any = None,
):
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    if page == 0:
        page = len(pages) - 1  # Loop around to the last item
    else:
        page -= 1
    return await menu(
        ctx=ctx,
        pages=pages,
        controls=controls,
        message=message,
        page=page,
        timeout=timeout,
        payload=payload,
    )


async def close_menu(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
    payload: Any = None,
):
    with contextlib.suppress(discord.NotFound):
        await message.delete()


def with_emojis(
    emojis: Sequence[Union[str, discord.Emoji, discord.PartialEmoji]],
    message: Optional[discord.Message] = None,
    user: Optional[discord.abc.User] = None,
) -> Callable:
    """
    Construct a reaction event check function for the menu system
    """

    def check(r: discord.Reaction, u: discord.abc.User):
        return (message == r.message) and (user == u) and (str(r.emoji) in emojis)

    return check


def with_channel(ctx: commands.Context) -> Callable:
    """
    Construct a message event check function for getting user reply
    """

    def check(m: discord.Message):
        return (ctx.channel == m.channel) and (ctx.author == m.author)

    return check


DEFAULT_CONTROLS = {"⬅️": prev_page, "❌": close_menu, "➡️": next_page}


async def yes_or_no(
    ctx: commands.Context,
    message: discord.Message,
    reactions: Iterable[_ReactableEmoji] = ("✅", "❌"),
    timeout: float = 120.0,
) -> Union[bool, None]:
    """
    A true/false reaction option for a message

    This function returns True if the first emoji is selected, else False
    or None if the wait_for action times out

    Parameters
    ----------
    ctx: commands.Context
        The command context
    message: discord.Message
        The message to react to (required)
    reactions: Tuple[_ReactableEmoji]
        The emojis to react with. Tuple must be 1 or 2 items long.
        The first item will be evaluated as True and the second item will be evaluated as False
    timeout: float
        The time (in seconds) to wait for a reaction

    Returns
    -------
    Boolean
        True or False depending on which emoji is reacted with
    None
        if the action times out
    """
    # Exit if bot does not have permission to add reactions
    if not message.channel.permissions_for(ctx.me).add_reactions:
        return
    if len(reactions) not in (1, 2):
        return
    # Add reactions
    start_adding_reactions(message, reactions)
    # Wait for reactions
    try:
        react, _ = await ctx.bot.wait_for(
            "reaction_add",
            check=with_emojis(tuple(reactions), message, ctx.author),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        if not ctx.me:
            return
        try:
            if message.channel.permissions_for(ctx.me).manage_messages:
                await message.clear_reactions()
            else:
                raise RuntimeError
        except (discord.Forbidden, RuntimeError):  # Cancel if cannot manage messages
            for reaction in reactions:
                try:
                    await message.remove_reaction(reaction, ctx.bot.user)
                except discord.Forbidden:
                    return
                except discord.HTTPException:
                    pass
        except discord.NotFound:
            return
    else:
        index = reactions.index(str(react.emoji))
        if len(reactions) == 2:
            return (True, False)[index]


async def get_user_reply(ctx: commands.Context, timeout: float = 180.0) -> Union[str, None]:
    """
    Function for getting a reply from a user

    Parameters
    ----------
    ctx: commands.Context
        The command context
    timeout: float
        The time (in seconds) to wait for a reply

    Returns
    -------
    String
        The message content
    None
        if the wait_for action times out
    """
    try:
        msg = await ctx.bot.wait_for("message", check=with_channel(ctx), timeout=timeout)
    except asyncio.TimeoutError:
        return None
    else:
        return msg.content
