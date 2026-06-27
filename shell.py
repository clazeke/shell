import sys
import os
import subprocess
import readline
import re

completions = {}
shell_variables = {}
activity_counter = 0
jobs_list = []
history_list = []
history_last_appended = 0

def completer(text, state):
    line = readline.get_line_buffer()

    parts = line.split()
    if parts:
        command_name = parts[0]
        completing_argument = len(parts) > 1 or line.endswith(' ')
        if completing_argument and command_name in completions:
            script_path = completions[command_name]
            current_word = parts[-1] if not line.endswith(' ') else ''
            previous_word = parts[-2] if len(parts) >= 2 and not line.endswith(' ') else (parts[-1] if len(parts) >= 2 else '')

            comp_env = os.environ.copy()
            comp_env['COMP_LINE'] = line
            comp_env['COMP_POINT'] = str(len(line.encode('utf-8')))
            result = subprocess.run(
                [script_path, command_name, current_word, previous_word],
                capture_output=True, text=True,
                env=comp_env
            )
            candidates = result.stdout.splitlines()
            if state < len(candidates):
                return candidates[state] + ' '
            return None

    begidx = readline.get_begidx()

    full_token = line[begidx:].split()[0] if line[begidx:].split() else text

    if begidx > 0:
        if '/' in full_token:
            dir_part, prefix = full_token.rsplit('/', 1)
            dir_part = dir_part + '/'
            try:
                entries = os.listdir(dir_part)
            except OSError:
                entries = []
            matches = []
            for e in entries:
                if e.startswith(prefix):
                    full_path = dir_part + e
                    #suffix = full_path[len(full_token):]
                    if os.path.isdir(full_path):
                        matches.append(full_path + '/')
                    else:
                        matches.append(full_path + ' ')
        else:
            try:
                files = os.listdir('.')
            except OSError:
                files = []
            matches = []
            for f in files:
                if f.startswith(full_token):
                    #suffix = f[len(full_token):]
                    if os.path.isdir(f):
                        matches.append(f + '/')
                    else:
                        matches.append(f + ' ')
        if not matches and state == 0:
            sys.stdout.write('\x07')
            sys.stdout.flush()
            return None
        
        if state < len(matches):
            return matches[state]
        return None
    
    builtins = ['echo', 'exit', 'type', 'pwd', 'cd']
    matches = [cmd for cmd in builtins if cmd.startswith(text)]

    path_dirs = os.environ.get('PATH', '').split(os.pathsep)
    for directory in path_dirs:
        if not os.path.isdir(directory):
            continue
        try:
            for filename in os.listdir(directory):
                if filename.startswith(text):
                    full_path = os.path.join(directory, filename)
                    if os.access(full_path, os.X_OK):
                        if filename not in matches:
                            matches.append(filename)
        except PermissionError:
            continue

    if state < len(matches):
        return matches[state] + ' '
    return None

readline.set_completer(completer)
readline.parse_and_bind("tab: complete")
readline.set_completer_delims(' \t\n')
#readline.set_completer_delims(readline.get_completer_delims().replace('/', ''))

def parse_command(command):
    tokens = []
    current_token = []
    in_single_quote = False
    in_double_quote = False
    token_started = False
    escaping = False
    dq_escaping = False

    for char in command:
        if escaping:
            current_token.append(char)
            token_started = True
            escaping = False

        elif in_single_quote:
            if char == "'":
                in_single_quote = False
            else:
                current_token.append(char)

        elif in_double_quote:
            if dq_escaping:
                if char == '"' or char == '\\':
                    current_token.append(char)
                else:
                    current_token.append('\\')
                    current_token.append(char)
                dq_escaping = False
            elif char == '\\':
                dq_escaping = True
            elif char == '"':
                in_double_quote = False
            else:
                current_token.append(char)
        
        else:
            if char == '\\':
                escaping = True
                token_started = True
            elif char == "'":
                in_single_quote = True
                token_started = True
            elif char == '"':
                in_double_quote = True
                token_started = True
            elif char == ' ':
                if token_started:
                    tokens.append(''.join(current_token))
                    current_token = []
                    token_started = False
            else:
                current_token.append(char)
                token_started = True
    if token_started:
        tokens.append(''.join(current_token))

    return tokens

def expand_variables(parts):
    expanded = []

    for token in parts:
        if not re.search(r'\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\}', token):
            expanded.append(token)
            continue

        result = re.sub(
            r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)',
            lambda m: shell_variables.get(m.group(1) or m.group(2), os.environ.get(m.group(1) or m.group(2), '')),
            token
        )

        if result == '' and re.fullmatch(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*', token):
            continue
            
        #words = result.split()
        #expanded.extend(words if words else [''])

        if result != '':
            expanded.append(result)
        
    return expanded

def compute_markers(job):
    ordered = sorted(
        job,
        key=lambda j: j["last_active"],
        reverse=True
    )

    markers = {}

    if len(ordered) >= 1:
        markers[id(ordered[0])] = '+'
    
    if len(ordered) >= 2:
        markers[id(ordered[1])] = '-'

    return markers

def reap_jobs():
    global jobs_list

    marker_snapshot = compute_markers(jobs_list)

    reaped = []
    still_running = []

    for job in jobs_list:
        ret = job["proc"].poll()

        if ret is not None:
            job["status"] = "Done"
            reaped.append(job)
        else:
            still_running.append(job)
    
    if not reaped:
        jobs_list[:] = still_running
        return [], marker_snapshot
    
    reaped_lines = []

    for job in reaped:
        marker = marker_snapshot.get(id(job), ' ')

        cmd = job["cmd"]
        if cmd.endswith(" &"):
            cmd = cmd[:-2]

        status_field = "Done".ljust(24)

        reaped_lines.append(
            (marker, job["num"], status_field, cmd)
        )

    jobs_list[:] = still_running

    return reaped_lines, marker_snapshot

def get_next_job_number():
    used_numbers = set()

    for job in jobs_list:
        used_numbers.add(job["num"])

    num = 1

    while num in used_numbers:
        num += 1

    return num

def execute_builtin(parts):
    built_in = ['echo', 'type', 'exit', 'pwd', 'cd', 'complete', 'jobs', 'history', 'declare']

    prog_name = parts[0]

    if prog_name == 'echo':
        return " ".join(parts[1:]) + "\n"
    
    elif prog_name == 'pwd':
        return os.getcwd() + "\n"
    
    elif prog_name == 'type':
        arg = " ".join(parts[1:])

        if arg in built_in:
            return arg + " is a shell builtin\n"
        
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)

        for directory in path_dirs:
            full_path = os.path.join(directory, arg)

            if os.path.exists(full_path) and os.access(full_path, os.X_OK):
                return arg + " is " + full_path + "\n"
            
        return arg + ": not found\n"
    
    elif prog_name == "cd":
        return ""
    
    elif prog_name == "history":
        if len(parts) >= 3 and parts[1] == "-r":
            file_path = parts[2]

            try:
                with open(file_path, "r") as f:
                    for line in f:
                        line = line.rstrip("\n")

                        history_list.append(line)
            
            except FileNotFoundError:
                return f"history: {file_path}: No such file\n"

        if len(parts) >= 3 and parts[1] == "-w":
                file_path = parts[2]

                with open(file_path, "w") as f:
                    for cmd in history_list:
                        f.write(cmd + "\n")
                return ""
        
        if len(parts) >= 3 and parts[1] == "-a":
            global history_last_appended
            file_path = parts[2]
            new_commands = history_list[history_last_appended:]
            with open(file_path, "a") as f:
                for cmd in new_commands:
                    f.write(cmd + "\n")
            history_last_appended = len(history_list)
            return ""
        
        n = None

        if len(parts) >= 2 and parts[1].isdigit():
            n = int(parts[1])

        if n is None:
            selected_history = history_list
            start_index = 0
        else:
            selected_history = history_list[-n:]
            start_index = len(history_list) - len(selected_history)

        output = []
        for i, cmd in enumerate(selected_history, start=start_index + 1):
            output.append(f"{i}  {cmd}")
        return "\n".join(output) + "\n"
    
    return ""

def split_pipeline(parts):
    commands = []
    current = []

    for token in parts:
        if token == "|":
            commands.append(current)
            current = []
        else:
            current.append(token)

    commands.append(current)

    return commands

def main():
    global activity_counter, jobs_list, history_last_appended
    built_in = ['echo', 'type', 'exit', 'pwd', 'cd', 'complete', 'jobs', 'history', 'declare']

    histfile = os.environ.get('HISTFILE')
    if histfile:
        try:
            with open(histfile, 'r') as f:
                for line in f:
                    line = line.rstrip('\n')
                    if line:
                        history_list.append(line)
        except FileNotFoundError:
            pass
    history_last_appended = len(history_list)
    
    while True:
        reaped_lines, _ = reap_jobs()
        for (marker, num, status_field, cmd) in reaped_lines:
            sys.stdout.write(f"[{num}]{marker}  {status_field}{cmd}\n")
            sys.stdout.flush()
        
        command = input("$ ")
        parts = parse_command(command)

        if not parts:
            continue

        history_list.append(command)
        parts = expand_variables(parts)

        if not parts:
            continue

        if "|" in parts:
            pipeline_commands = split_pipeline(parts)

            processes = []
            previous_stdout = None

            for i, cmd in enumerate(pipeline_commands):
                is_last = (i == len(pipeline_commands) - 1)

                prog_name = cmd[0]
                is_builtin = prog_name in built_in

                if is_builtin:
                    output_text = execute_builtin(cmd)
                    if output_text is None:
                        output_text = ""

                    if is_last:
                        sys.stdout.write(output_text)
                        sys.stdout.flush()
                        continue

                    proc = subprocess.Popen(
                        ["cat"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        text=True
                    )

                    proc.stdin.write(output_text)
                    proc.stdin.close()

                    previous_stdout = proc.stdout
                    processes.append(proc)
                    continue

                proc = subprocess.Popen(
                    cmd,
                    stdin=previous_stdout,
                    stdout=None if is_last else subprocess.PIPE,
                    text=True
                )

                if previous_stdout:
                    previous_stdout.close()

                previous_stdout = proc.stdout
                processes.append(proc)

            for proc in processes:
                proc.wait()

            continue

        output_file = None
        error_file = None
        append_output = False
        append_error = False

        stdout_operators = {'>', '1>'}
        append_operators = {'>>', '1>>'}

        i = 0
        while i < len(parts):
            token = parts[i]
            if token in stdout_operators:
                if i + 1 < len(parts):
                    output_file = parts[i + 1]
                parts = parts[:i] + parts[i + 2:]
            elif token in append_operators:
                if i + 1 < len(parts):
                    output_file = parts[i + 1]
                    append_output = True
                parts = parts[:i] + parts[i + 2:]
            elif token == '2>':
                if i + 1 < len(parts):
                    error_file = parts[i + 1]
                parts = parts[:i] + parts[i + 2:]
            elif token == '2>>':
                if i + 1 < len(parts):
                    error_file = parts[i + 1]
                    append_error = True
                parts = parts[:i] + parts[i + 2:]
            else:
                i += 1
        
        if not parts:
            continue

        if output_file:
            mode = 'a' if append_output else 'w'
            out = open(output_file, mode)
        else:
            out = None
        err_out = open(error_file, 'a' if append_error else 'w') if error_file else None

        output_stream = out if out else sys.stdout
        error_stream = err_out if err_out else sys.stderr

        prog_name = parts[0]
        arguments = parts

        if prog_name == 'exit':
            break
        elif prog_name == 'echo':
            output_stream.write(" ".join(parts[1:]) + '\n')
        elif prog_name == 'type':
            arg = " ".join(parts[1:])
            if arg in built_in:
                output_stream.write(arg + ' is a shell builtin\n')
            else:
                path_dirs = os.environ.get('PATH', '').split(os.pathsep)
                for directory in path_dirs:
                    full_path = os.path.join(directory, arg)
                    if os.path.exists(full_path) and os.access(full_path, os.X_OK):
                        output_stream.write(arg + ' is ' + full_path + '\n')
                        break
                else:
                    output_stream.write(arg + ': not found\n')
        elif prog_name == 'pwd':
            output_stream.write(os.getcwd() + '\n')
        elif prog_name == 'cd':
            target_directory = parts[1]
            if target_directory == '~':
                    target_directory = os.environ.get('HOME')
            if os.path.isdir(target_directory):
                os.chdir(target_directory)
            else:
                error_stream.write('cd: ' + target_directory + ': No such file or directory\n')
        elif prog_name == 'complete':
            if len(parts) >= 4 and parts[1] == '-C':
                script_path = parts[2]
                command_name = parts[3]
                completions[command_name] = script_path
            elif len(parts) >= 3 and parts[1] == '-p':
                command_name = parts[2]
                if command_name in completions:
                    script_path = completions[command_name]
                    output_stream.write(f"complete -C '{script_path}' {command_name}\n")
                else:
                    error_stream.write(f"complete: {command_name}: no completion specification\n")
            elif len(parts) >= 3 and parts[1] == '-r':
                command_name = parts[2]
                completions.pop(command_name, None)
        elif prog_name == 'jobs':
            reaped_lines, marker_snapshot = reap_jobs()

            all_lines = []

            for (marker, num, status_field, cmd) in reaped_lines:
                all_lines.append(
                    (num, marker, status_field, cmd)
                )

            for job in jobs_list:
                marker = marker_snapshot.get(id(job), ' ')

                status_field = job["status"].ljust(24)

                all_lines.append(
                    (job["num"], marker, status_field, job["cmd"])
                )

            all_lines.sort(key=lambda x: x[0])

            for (num, marker, status_field, cmd) in all_lines:
                output_stream.write(f"[{num}]{marker}  {status_field}{cmd}\n")
            
        elif prog_name == 'history':
            if len(parts) >= 3 and parts[1] == "-r":
                file_path = parts[2]

                try:
                    with open(file_path, "r") as f:
                        for line in f:
                            line = line.rstrip("\n")
                            history_list.append(line)
                except FileNotFoundError:
                    output_stream.write(f"history: {file_path}: No such file\n")
                continue
            
            if len(parts) >= 3 and parts[1] == "-w":
                file_path = parts[2]

                with open(file_path, "w") as f:
                    for cmd in history_list:
                        f.write(cmd + "\n")
                continue

            if len(parts) >= 3 and parts[1] == "-a":
                file_path = parts[2]
                new_commands = history_list[history_last_appended:]
                with open(file_path, "a") as f:
                    for cmd in new_commands:
                        f.write(cmd + "\n")
                history_last_appended = len(history_list)
                continue

            n = None

            if len(parts) >= 2 and parts[1].isdigit():
                n = int(parts[1])

            if n is None:
                start_index = 0
                selected_history = history_list
            else:
                selected_history = history_list[-n:]
                start_index = len(history_list) - len(selected_history)

            for i, cmd in enumerate(selected_history, start=start_index + 1):
                output_stream.write(f"{i}  {cmd}\n")
        
        elif prog_name == 'declare':
            if len(parts) >= 3 and parts[1] == '-p':
                if len(parts) >= 3:
                    var_name = parts[2]
                    if var_name in shell_variables:
                        value = shell_variables[var_name]
                        output_stream.write(f'declare -- {var_name}="{value}"\n')
                    else:
                        error_stream.write(f"declare: {var_name}: not found\n")
            elif len(parts) >= 2 and '=' in parts[1]:
                assignment = parts[1]
                name, value = assignment.split('=', 1)
                if not name or not (name[0].isalpha() or name[0] == '_') or not all(c.isalnum() or c == '_' for c in name[1:]):
                    error_stream.write(f"declare: `{assignment}': not a valid identifier\n")
                else:
                    shell_variables[name] = value
        
        else:
            run_in_background = False
            if arguments and arguments[-1] == '&':
                run_in_background = True
                arguments = arguments[:-1]

            path_dirs = os.environ.get('PATH', '').split(os.pathsep)
            found_path = None
            for directory in path_dirs:
                full_path = os.path.join(directory, prog_name)
                if os.path.exists(full_path) and os.access(full_path, os.X_OK):
                    found_path = full_path
                    break
            if found_path:
                if run_in_background:
                    job_num = get_next_job_number()
                    proc = subprocess.Popen(
                        arguments,
                        stdout=out if out else None,
                        stderr=err_out if err_out else None
                    )
                    cmd_str = " ".join(arguments) + " &"

                    activity_counter += 1

                    new_job = {
                        "num": job_num,
                        "pid": proc.pid,
                        "proc": proc,
                        "cmd": cmd_str,
                        "status": "Running",
                        "last_active": activity_counter
                    }
                    jobs_list.append(new_job)
                    
                    sys.stdout.write(f"[{job_num}] {proc.pid}\n")
                    sys.stdout.flush()
                else:
                    subprocess.run(
                        arguments,
                        stdout=out if out else None,
                        stderr=err_out if err_out else None
                        )
            else:
                sys.stdout.write(f"{prog_name}: command not found\n")

        if out is not None:
            out.close()
        if err_out is not None:
            err_out.close()

        
    if histfile:
        new_commands = history_list[history_last_appended:]
        with open(histfile, 'a') as f:
            for cmd in new_commands:
                f.write(cmd + '\n')


if __name__ == "__main__":
    main()
