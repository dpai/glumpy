# ----------------------------------------------------------------------------
# pyglet
# Copyright (c) 2006-2008 Alex Holkner
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

''' Event dispatch framework (adapted from pyglet).

All objects that produce events in glumpy implement `EventDispatcher`,
providing a consistent interface for registering and manipulating event
handlers.  A commonly used event dispatcher is `glumpy.window.Window`.

Event types
===========

For each event dispatcher there is a set of events that it dispatches; these
correspond with the type of event handlers you can attach.  Event types are
identified by their name, for example, ''on_resize''.  If you are creating a
new class which implements `EventDispatcher`, you must call
`EventDispatcher.register_event_type` for each event type.

Attaching event handlers
========================

An event handler is simply a function or method.  You can attach an event
handler by setting the appropriate function on the instance::

    def on_resize(width, height):
        # ...
    dispatcher.on_resize = on_resize

There is also a convenience decorator that reduces typing::

    @dispatcher.event
    def on_resize(width, height):
        # ...

You may prefer to subclass and override the event handlers instead::

    class MyDispatcher(DispatcherClass):
        def on_resize(self, width, height):
            # ...

Event handler stack
===================

When attaching an event handler to a dispatcher using the above methods, it
replaces any existing handler (causing the original handler to no longer be
called).  Each dispatcher maintains a stack of event handlers, allowing you to
insert an event handler "above" the existing one rather than replacing it.

There are two main use cases for "pushing" event handlers:

* Temporarily intercepting the events coming from the dispatcher by pushing a
  custom set of handlers onto the dispatcher, then later "popping" them all
  off at once.
* Creating "chains" of event handlers, where the event propogates from the
  top-most (most recently added) handler to the bottom, until a handler
  takes care of it.

Use `EventDispatcher.push_handlers` to create a new level in the stack and
attach handlers to it.  You can push several handlers at once::

    dispatcher.push_handlers(on_resize, on_key_press)

If your function handlers have different names to the events they handle, use
keyword arguments::

    dispatcher.push_handlers(on_resize=my_resize,
                             on_key_press=my_key_press)

After an event handler has processed an event, it is passed on to the
next-lowest event handler, unless the handler returns `EVENT_HANDLED`, which
prevents further propogation.

To remove all handlers on the top stack level, use
`EventDispatcher.pop_handlers`.

Note that any handlers pushed onto the stack have precedence over the
handlers set directly on the instance (for example, using the methods
described in the previous section), regardless of when they were set.
For example, handler ``foo`` is called before handler ``bar`` in the following
example::

    dispatcher.push_handlers(on_resize=foo)
    dispatcher.on_resize = bar

Dispatching events
==================

glumpy uses a single-threaded model for all application code.  Event
handlers are only ever invoked as a result of calling
EventDispatcher.dispatch_events`.

It is up to the specific event dispatcher to queue relevant events until they
can be dispatched, at which point the handlers are called in the order the
events were originally generated.

This implies that your application runs with a main loop that continously
updates the application state and checks for new events::

    while True:
        dispatcher.dispatch_events()
        # ... additional per-frame processing

Not all event dispatchers require the call to ``dispatch_events``; check with
the particular class documentation.

'''
from sys import version_info;
if version_info[0]==3:
    unicode = str
__docformat__ = 'restructuredtext'
__version__ = '$Id: event.py 2319 2008-10-12 02:50:08Z Alex.Holkner $'

import inspect

EVENT_HANDLED = True
EVENT_UNHANDLED = None

class EventException(Exception):
    '''An exception raised when an event handler could not be attached.
    '''
    pass

class EventDispatcher(object):
    '''Generic event dispatcher interface.

    See the module docstring for usage.
    '''
    # Placeholder empty stack; real stack is created only if needed
    _event_stack = ()

    @classmethod
    def register_event_type(cls, name):
        '''Register an event type with the dispatcher.

        Registering event types allows the dispatcher to validate event
        handler names as they are attached, and to search attached objects for
        suitable handlers.

        :param string name:
            Name of the event to register.

        '''
        if not hasattr(cls, 'event_types'):
            cls.event_types = []
        cls.event_types.append(name)
        return name

    def attach(self, *args, **kwargs):
        '''Push a level onto the top of the handler stack, then attach zero or
        more event handlers.

        If keyword arguments are given, they name the event type to attach.
        Otherwise, a callable's `__name__` attribute will be used.  Any other
        object may also be specified, in which case it will be searched for
        callables with event names.
        '''

        self.push_handlers(*args, **kwargs)


    def push_handlers(self, *args, **kwargs):
        '''Push a level onto the top of the handler stack, then attach zero or
        more event handlers.

        If keyword arguments are given, they name the event type to attach.
        Otherwise, a callable's `__name__` attribute will be used.  Any other
        object may also be specified, in which case it will be searched for
        callables with event names.
        '''
        # Create event stack if necessary
        if type(self._event_stack) is tuple:
            self._event_stack = []

        # Place dict full of new handlers at beginning of stack
        self._event_stack.insert(0, {})
        self.set_handlers(*args, **kwargs)

    def _get_handlers(self, args, kwargs):
        '''Implement handler matching on arguments for set_handlers and
        remove_handlers.
        '''
        for object in args:
            if inspect.isroutine(object):
                # Single magically named function
                name = object.__name__
                if name not in self.event_types:
                    raise EventException('Unknown event "%s"' % name)
                yield name, object
            else:
                # Single instance with magically named methods
                for name in dir(object):
                    if name in self.event_types:
                        yield name, getattr(object, name)
        for name, handler in kwargs.items():
            # Function for handling given event (no magic)
            if name not in self.event_types:
                raise EventException('Unknown event "%s"' % name)
            yield name, handler

    def set_handlers(self, *args, **kwargs):
        '''
        Attach one or more event handlers to the top level of the handler
        stack.

        See `push_handlers` for the accepted argument types.
        '''

        # Create event stack if necessary
        if type(self._event_stack) is tuple:
            self._event_stack = [{}]

        for name, handler in self._get_handlers(args, kwargs):
            self.set_handler(name, handler)

    def set_handler(self, name, handler):
        '''Attach a single event handler.

        :param string name:
            Name of the event type to attach to.

        :param callable handler:
            Event handler to attach.
        '''
        # Create event stack if necessary
        if type(self._event_stack) is tuple:
            self._event_stack = [{}]

        self._event_stack[0][name] = handler

    def pop_handlers(self):
        '''
        Pop the top level of event handlers off the stack.
        '''
        assert self._event_stack and 'No handlers pushed'

        del self._event_stack[0]

    def remove_handlers(self, *args, **kwargs):
        '''Remove event handlers from the event stack.

        See push_handlers for the accepted argument types.  All handlers
        are removed from the first stack frame that contains any of the given
        handlers.  No error is raised if any handler does not appear in that
        frame, or if no stack frame contains any of the given handlers.

        If the stack frame is empty after removing the handlers, it is
        removed from the stack.  Note that this interferes with the expected
        symmetry of push_handlers and pop_handlers.
        '''
        handlers = list(self._get_handlers(args, kwargs))

        # Find the first stack frame containing any of the handlers
        def find_frame():
            for frame in self._event_stack:
                for name, handler in handlers:
                    try:
                        if frame[name] == handler:
                            return frame
                    except KeyError:
                        pass
        frame = find_frame()

        # No frame matched; no error.
        if not frame:
            return

        # Remove each handler from the frame.
        for name, handler in handlers:
            try:
                if frame[name] == handler:
                    del frame[name]
            except KeyError:
                pass

        # Remove the frame if it's empty.
        if not frame:
            self._event_stack.remove(frame)

    def remove_handler(self, name, handler):
        '''Remove a single event handler.

        The given event handler is removed from the first handler stack frame
        it appears in.  The handler must be the exact same callable as passed
        to `set_handler`, `set_handlers` or `push_handlers`; and the name
        must match the event type it is bound to.

        No error is raised if the event handler is not set.

        :param string name:
             Name of the event type to remove.

        :param callable handler:
             Event handler to remove.
        '''
        for frame in self._event_stack:
            try:
                if frame[name] is handler:
                    del frame[name]
                    break
            except KeyError:
                pass

    def get_handler(self, name):
        '''Get a single event handler by name.

        Returns the first handler function that matches name.

	Raises KeyError if name is not found.

        :param string name:
             Name of the event type to get.

        '''
        for frame in self._event_stack:
            try:
                return frame[name]
            except KeyError:
                pass

        raise KeyError('Event handler {} not found.'.format(name))

    def dispatch_event(self, event_type, *args):
        '''Dispatch a single event to the attached handlers.

        The event is propogated to all handlers from from the top of the stack
        until one returns True. This method should be used only by
        EventDispatcher implementors; applications should call the
        dispatch_events method.


        :param string event_type:
            Name of the event.

        :param sequence args:
            Arguments to pass to the event handler.

        :rtype: bool or None
        :return:
            True if an event handler returned True; False if one or more event
            handlers were invoked but returned only Fasle.
        '''
        assert event_type in self.event_types

        invoked = False

        #if event_type == "on_draw":
        #    print self._event_stack[0]["on_draw"]

        # Search handler stack for matching event handlers
        for frame in list(self._event_stack):
            handler = frame.get(event_type, None)
            if handler:
                try:
                    invoked = True
                    if handler(*args):
                        return EVENT_HANDLED
                except TypeError:
                    self._raise_dispatch_exception(event_type, args, handler)


        # Check instance for an event handler
        if hasattr(self, event_type):
            try:
                invoked = True
                if getattr(self, event_type)(*args):
                    return EVENT_HANDLED
            except TypeError:
                self._raise_dispatch_exception(
                    event_type, args, getattr(self, event_type))

        if invoked:
            return EVENT_UNHANDLED

        return False

    def _raise_dispatch_exception(self, event_type, args, handler):
        # A common problem in applications is having the wrong number of
        # arguments in an event handler.  This is caught as a TypeError in
        # dispatch_event but the error message is obfuscated.
        #
        # Here we check if there is indeed a mismatch in argument count,
        # and construct a more useful exception message if so.  If this method
        # doesn't find a problem with the number of arguments, the error
        # is re-raised as if we weren't here.

        n_args = len(args)

        # Inspect the handler
        handler_args, handler_varargs, _, handler_defaults = \
            inspect.getargspec(handler)
        n_handler_args = len(handler_args)

        # Remove "self" arg from handler if it's a bound method
        if inspect.ismethod(handler) and handler.__self__:
            n_handler_args -= 1

        # Allow *args varargs to overspecify arguments
        if handler_varargs:
            n_handler_args = max(n_handler_args, n_args)

        # Allow default values to overspecify arguments
        if (n_handler_args > n_args and
            handler_defaults and
            n_handler_args - len(handler_defaults) <= n_args):
            n_handler_args = n_args

        if n_handler_args != n_args:
            if inspect.isfunction(handler) or inspect.ismethod(handler):
                descr = '%s at %s:%d' % (
                    handler.func_name,
                    handler.func_code.co_filename,
                    handler.func_code.co_firstlineno)
            else:
                descr = repr(handler)

            raise TypeError(
                '%s event was dispatched with %d arguments, but '
                'handler %s has an incompatible function signature' %
                (event_type, len(args), descr))
        else:
            raise

    def event(self, *args):
        '''Function decorator for an event handler.

        Usage::

            win = window.Window()

            @win.event
            def on_resize(self, width, height):
                # ...

        or::

            @win.event('on_resize')
            def foo(self, width, height):
                # ...

        '''
        if len(args) == 0:                      # @window.event()
            def decorator(func):
                name = func.__name__
                self.set_handler(name, func)
                return func
            return decorator
        elif inspect.isroutine(args[0]):        # @window.event
            func = args[0]
            name = func.__name__
            self.set_handler(name, func)
            return args[0]
        elif type(args[0]) in (str, unicode):   # @window.event('on_resize')
            name = args[0]
            def decorator(func):
                self.set_handler(name, func)
                return func
            return decorator
