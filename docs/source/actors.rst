Actors
======

Sometimes we want our application to be doing two things at the same time, or
at least have the appearance of doing so. As a typical example, suppose we want
to constantly collect some signals describing an experimental apparatus
(the sample temperature, pressure of a vacuum chamber, ambient
temperature or humidity) even when we aren't collecting data.

Sometimes, if we are unlucky, these separate bits of the program might have to
manage their own data and *internal state*. Sometimes, if we are very unlucky,
we might have to make these separately running pieces of our application *talk
to each other* in order for them to work.

A relatively simple way of thinking about this problem is to imagine the
separately running processes which coordinate with each other by passing messages
to each other, this allows communication to happen whenever it is safe or
meaningful for it to happen.

Declaring Actors
----------------

autodidaqt provides an Actor class (``autodidaqt.actors.Actor``) which you can use to write
asynchronous bits of code that run alongside the rest of your program. Because an Actor is
a Python object, it can have any internal state it requires. An ``Actor`` in autodidaqt is
distinguished by the presence of two asynchronous methods :py:meth:`~autodidaqt.actors.Actor.prepare`
and :py:meth:`~autodidaqt.actors.Actor.run`.

.. code-block:: python

    class Actor:
        ...

        async def prepare(self):
            # handle any setup work here

        async def run(self):
            # do any useful work here, either once and quit,
            # or read messages continually

When you start autodidaqt you can specify any additional actors your program uses together
with unique IDs and autodidaqt will handle configuring and scheduling them to run for you.

You can see a full example of using actors in the examples.



**Technical note**: *Actors* in autodidaqt are actually closer to *agents* as
described by most concurrent programming frameworks.