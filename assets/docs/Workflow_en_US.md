# Workflow Editor Guide

> This document is AI-translated from the Simplified Chinese version. Last updated: 2026-09-24. If there is any discrepancy, the Simplified Chinese version prevails.

## When to use it

The workflow editor is a good fit for things like:

- Repeated clicking on a fixed screen.
- Simple automation that needs to branch on conditions.
- Combined actions such as loop detection, switching screens, pressing keys, waiting and notifications.
- Turning scattered operations into a small workflow you can reuse.

If a built-in home page task already covers your need, such as spending power, daily training or Divergent Universe, use that task instead.

The workflow editor is better suited to "custom supplementary logic".

## Core concepts

A workflow consists of multiple steps, organised as a tree.

- Normal steps: executed in order, for example Click Image, Click Text, Wait, Press Key.
- Mouse steps: support clicking a fixed coordinate, and dragging with the left button held from a start point to an end point.
- Control steps: can contain child steps. Currently `if`, `for` and `while` are supported.
- Loop control steps: `break` and `continue` can be used inside a loop.

Think of it as a visual "small script editor" that you can use without writing code.

## Getting there

Open the assistant and go to "Workflow" in the left navigation bar.

The screen is split into two parts:

- Top half: workflow list, run, stop, import/export, template capture and similar actions.
- Bottom half: the step tree, where you edit the step structure of the current workflow.

## Creating your first workflow

### New workflow

Click "New Workflow" and enter an easy-to-recognise name.

Official example workflows are normally read-only: you can view them but not modify them directly.

Workflows you create yourself can be edited, renamed, deleted and exported.

### Adding steps

Click "Add Step" to add a step at the current level.

If a control step such as `if`, `for` or `while` is selected, you can also click "Add Child Step" to attach the new step under that node.

### Editing and reordering

- Double-click a step, or click "Edit Step", to modify it.
- Click "Up" or "Move Down" to reorder steps at the same level.
- Right-click the step tree to run the whole workflow, or only the selected step.

## Common steps

### Click Image

Suited to screens with stable buttons, icons or dialogs.

Frequently used options:

- Template Path: the image asset to match.
- Image Threshold: matching precision.
- Detection Area: only search within a given area, which reduces false matches.
- Retry Count: how many times to retry when nothing is found.
- Click Action: click, press, release.
- Press Duration: only fill this in when a long press is needed; if left empty or 0, the default click behaviour is used.

### Click Text

Suited to cases where the button text is stable but the icon style changes often.

Frequently used options:

- Target Text: the text OCR should recognise.
- Use Contains Match: for when the target text may have extra content before or after it.
- Detection Area: limits the OCR search area.
- Retry Count: retries when nothing is found.
- Click Action and Press Duration: the same as Click Image.

### Click Coordinates

Suited to cases where the target position is fixed but there is no stable image or text to recognise.

The usual approach is to select an area with the capture tool first, then copy those coordinates into the step.

### Drag Mouse

Used to drag a list inside a menu, or to move the mouse with the left button held in the game screen.

- Drag Start and Drag End use normalised coordinates relative to the game window, for example `100 / 1920, 540 / 1080`.
- Drag Duration is 0 to 60 seconds and sets the speed from start to end; a longer duration moves more slowly.
- On execution it moves to the start point, presses the left mouse button, moves to the end point and then releases.
- In cloud game mode, browser pointer lock prevents rotating the camera with this step; menu dragging still needs to be verified in the actual game.

### Find Image / Find Text

These two steps do not click; they only determine whether the target exists.

They are commonly used in `if` or `while` conditions, for example:

- Only keep clicking when "Start Challenge" is detected.
- Keep looping and waiting while a certain warning image is not detected.

### Wait

The simplest delay step, useful as a buffer before a screen change, an animation or a button appearing.

### Press Key

Simulates a keyboard key. You can choose click, press or release, and configure the key duration.

### Switch Screen

This step calls the assistant's existing screen switching logic.

The target is not free-form: the screen must already be defined in the current program and be reachable from the `main` home screen.

If a screen is not in the dropdown, the current version cannot switch to it directly.

### Play Audio / Push Notification

These two steps are useful for alerting you at key moments:

- Play Audio: plays a local alert sound.
- Push Notification: sends text to your currently configured notification channels, optionally with a screenshot.

## Using control steps

### if

Runs the child steps below it when the condition holds.

Suited to logic like "if a certain button is visible, click it".

### for

Runs the child steps a fixed number of times.

Entering 0 for the loop count means an infinite loop, which you must end with a condition, the stop button or `break`.

### while

Keeps running the child steps as long as the condition holds.

It is recommended to also set a sensible maximum loop count, so an abnormal condition cannot run forever.

### break / continue

These two steps can only be placed inside a loop:

- `break`: ends the current loop.
- `continue`: skips the remaining steps of this round and starts the next loop immediately.

If they are placed outside a loop, the run log reports that the step is invalid.

## Capturing templates and coordinates

### Capture Image Template

Click "Capture Image Template" and the program opens the capture window.

After selecting an area and saving, the template is placed in the current workflow's own asset folder automatically.

Workflow assets are saved together with the workflow and are included when exporting.

### How to fill in Detection Area

If you have already selected an area with the capture tool, you can usually paste the generated coordinate expression straight into "Detection Area".

If it is left empty, the default is a full-screen search.

To improve stability, keep the detection area as small as possible and cover only where the target may appear.

## Running and debugging

### Run Workflow

Click "Run Workflow" to execute every step in the current workflow.

Workflows now run as a separate task on the log page, so you can force-stop them directly from the log page.

### Run Selected Step

Select a step in the step tree, then use the right-click menu to run "Run Selected Step".

This is ideal for debugging whether a node can correctly recognise an image, text or coordinate.

### Reading the log

When running, pay attention to the log page output:

- Which step is currently executing.
- Whether the condition evaluation succeeded.
- Whether the maximum loop count was reached.
- Whether exceptions, missing templates or unrecognised target text occurred.

## Import, export and asset folders

A workflow is saved as a folder and normally contains:

- `workflow.yaml`: the workflow structure itself.
- `templates/`: image template assets.

You can use "Export Workflow" to pack the whole workflow into a zip and share it.

You can also use "Import Workflow" to restore it into your own assistant.

## A simple example

Here is a very common approach:

1. `if` detects the text "Start Challenge".
2. When the condition holds, a child step runs "Click Text: Start Challenge".
3. `wait` for 1 second.
4. `while` detects whether a certain result prompt has not appeared yet.
5. The loop body waits 1 second each round, for at most a few rounds.
6. Once the result is recognised, play audio or send a message.

Build the workflow short and small first, confirm every step is stable, then add branches and loops gradually. The success rate is usually higher that way.

## Practical advice

- Prefer a smaller detection area; do not default to full-screen image search or full-screen OCR.
- Crop image templates down to stable features only, and avoid capturing moving backgrounds.
- Where text recognition works, try "Click Text" first.
- When debugging a single step, use "Run Selected Step" instead of running the whole workflow each time.
- If recognition is unstable, first check "Toolbox → Game Screenshot" to confirm the program is capturing the right screen.
- If you only want to automate built-in tasks, starting with the workflow editor is not recommended; maintenance costs will be higher.
