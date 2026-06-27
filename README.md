# Python Shell

A lightweight Unix-like shell implemented in Python. This project recreates many core features of a modern command-line shell, including built-in commands, command execution, pipelines, I/O redirection, background job control, command history, variable expansion, and programmable tab completion.

## Features

### Command Execution

* Execute external programs from the system `PATH`
* Execute shell built-in commands
* Automatic command lookup
* Graceful handling of unknown commands

### Built-in Commands

* `echo`
* `cd`
* `pwd`
* `exit`
* `type`
* `history`
* `jobs`
* `declare`
* `complete`

### Input Parsing

* Support for:

  * Single quotes (`'`)
  * Double quotes (`"`)
  * Escaped characters (`\`)
* Proper tokenization of command-line arguments

### Pipelines

Supports Unix-style pipelines.

Example:

```bash
ls | grep ".py"
```

Built-in commands can also participate in pipelines.

### Input/Output Redirection

Supported operators:

```bash
>
>>
1>
1>>
2>
2>>
```

Examples:

```bash
echo Hello > output.txt

ls >> files.txt

python script.py 2> errors.log
```

### Background Jobs

Run commands in the background using:

```bash
sleep 30 &
```

Features include:

* Job numbering
* Running/Done status
* Automatic cleanup of completed jobs
* `jobs` command
* Active job markers (`+` and `-`)

### Command History

Supports:

```bash
history
history 10
history -w file
history -a file
history -r file
```

History can also be loaded from and saved to the file specified by the `HISTFILE` environment variable.

### Shell Variables

Create variables:

```bash
declare NAME=John
```

Display variables:

```bash
declare -p NAME
```

Variable expansion:

```bash
echo $NAME
echo ${NAME}
```

Environment variables are expanded automatically if a shell variable does not exist.

### Programmable Tab Completion

Supports:

* Built-in command completion
* Executable completion from the system `PATH`
* File and directory completion
* Custom completion scripts

Register a completion script:

```bash
complete -C /path/to/script mycommand
```

Show a completion:

```bash
complete -p mycommand
```

Remove a completion:

```bash
complete -r mycommand
```

## Project Structure

```
.
├── shell.py
└── README.md
```

## Requirements

* Python 3.9+
* Unix/Linux/macOS (recommended)
* Windows may work with limited functionality depending on the availability of Unix commands such as `cat`.

## Running

Clone the repository:

```bash
git clone https://github.com/<your-username>/<repository>.git
```

Navigate into the project:

```bash
cd <repository>
```

Run the shell:

```bash
python shell.py
```

## Example Session

```text
$ pwd
/home/user

$ echo Hello World
Hello World

$ declare NAME=Alice

$ echo $NAME
Alice

$ ls | grep ".py"

$ sleep 15 &
[1] 12345

$ jobs
[1]+ Running                 sleep 15 &

$ history
```

## Learning Objectives

This project demonstrates concepts including:

* Process creation
* Subprocess management
* Command parsing
* Shell design
* Inter-process communication
* Pipes
* I/O redirection
* Job control
* Environment variables
* Command history
* Auto-completion
* Operating system fundamentals

## Future Improvements

* Signal handling (`Ctrl+C`, `Ctrl+Z`)
* Command aliases
* Wildcard (glob) expansion
* Command substitution
* Scripting support
* Improved POSIX compatibility
* Syntax highlighting
* Configuration file support

