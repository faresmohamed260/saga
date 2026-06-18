$python = "B:\Documents\PyCharm\graduationProject\venv\Scripts\python.exe"
$script = "B:\Documents\PyCharm\graduationProject\integrations\comfyui\run_gateway.py"
$taskName = "ModalComfyUIGateway"
$action = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory "B:\Documents\PyCharm\graduationProject"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Start the Modal ComfyUI local gateway at logon." -Force
Start-ScheduledTask -TaskName $taskName
