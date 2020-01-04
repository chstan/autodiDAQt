Why should I use DAQuiri?
=========================

Most scientific experiments use National Instruments' LabView to script their data
acquisition software, many rightly. LabView provides an amazing runtime environment and hardware support, but
it also provides an inflexible programming language and a frustrating IDE.

Most scientific experiments are also boring at the level of their software. For the most part
in scientific data acquisition, we adjust a few parameters of our experiment, wait until everything
has calmed down (that delay line or source-measure unit might be quick, but heat takes a while to move!), and collect some data.
Our software repeats this process a few hundred or thousand times while we drink coffee or read a paper and then
we open our data in Matlab/Python/Julia/{Proprietary Analysis Environment}.exe at the other end. Repeat *ad infinitum*
and maybe if we're into our second coffee we want to browse the data as it's being collected and do some light (*light*)
data analysis live.

If at its core your experiment's software isn't miles more complicated than this, keep reading and you might be able to
scrap that LabView license.

What's possible with DAQuiri
----------------------------

DAQuiri wraps all your scientific hardware in a uniform asynchronous interface:
axes are anything you can read from (their position), configure, and *maybe* write to (move).
This includes your lock-in amplifiers, your cameras, and your electron spectrometers--all read only--
not just your motion controllers.

Once you've done this, DAQuiri only asks you specify what sequence of motions and data collection you need
(this is *your* experiment so no assumption here, but we make simple) and it will handle:

1. UI generation for your experiment's degrees of freedom
2. Front panels for your instruments
3. Data I/O and collation
4. Plotting intermediate data
5. Full records of what actually happened to collect any piece of data, down to adjustments of instrument
   properties with millisecond timestamps
6. Conveniences like pause/resume, estimated completion times, notifications on error/finish,
   scan queueing, and more

All this said, DAQuiri doesn't make any assumptions about what you need, you can do full-fledged UI
programming and whatever else you need, keeping abstractions at whatever level is appropriate for your work.

The science is hard enough.
