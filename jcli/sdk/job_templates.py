"""Job XML template generation for parameterized job creation."""

from __future__ import annotations


def generate_freestyle_xml(
    git_url: str = "",
    git_branch: str = "main",
    shell_script: str = "",
    description: str = "",
    cron_schedule: str = "",
) -> str:
    """Generate XML for a Freestyle project."""
    triggers_xml = ""
    if cron_schedule:
        triggers_xml = f"""
  <triggers>
    <hudson.triggers.TimerTrigger>
      <spec>{cron_schedule}</spec>
    </hudson.triggers.TimerTrigger>
  </triggers>"""

    scm_xml = ""
    if git_url:
        scm_xml = f"""
  <scm class="hudson.plugins.git.GitSCM" plugin="git">
    <configVersion>2</configVersion>
    <userRemoteConfigs>
      <hudson.plugins.git.UserRemoteConfig>
        <url>{git_url}</url>
      </hudson.plugins.git.UserRemoteConfig>
    </userRemoteConfigs>
    <branches>
      <hudson.plugins.git.BranchSpec>
        <name>*/{git_branch}</name>
      </hudson.plugins.git.BranchSpec>
    </branches>
    <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
  </scm>"""

    builders_xml = ""
    if shell_script:
        builders_xml = f"""
  <builders>
    <hudson.tasks.Shell>
      <command>{_escape_xml(shell_script)}</command>
      <configuredLocalRules/>
    </hudson.tasks.Shell>
  </builders>"""

    return f"""<?xml version='1.1' encoding='UTF-8'?>
<project>
  <description>{_escape_xml(description)}</description>
  <keepDependencies>false</keepDependencies>
  <properties/>
{scm_xml}
  <canRoam>true</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
{triggers_xml}
  <concurrentBuild>false</concurrentBuild>
{builders_xml}
  <publishers/>
  <buildWrappers/>
</project>"""


def generate_pipeline_xml(
    git_url: str = "",
    git_branch: str = "main",
    jenkinsfile_path: str = "Jenkinsfile",
    description: str = "",
    script: str = "",
) -> str:
    """Generate XML for a Pipeline project.

    If ``script`` is provided the definition uses ``CpsFlowDefinition``
    (inline Pipeline script).  Otherwise when ``git_url`` is given the
    definition is ``CpsScmFlowDefinition`` (Pipeline script from SCM).
    """
    definition_xml: str
    if script:
        # Inline script mode (CpsFlowDefinition)
        definition_xml = f"""
    <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
      <script>{_escape_xml(script)}</script>
      <sandbox>true</sandbox>
    </definition>"""
    elif git_url:
        # SCM-based mode (CpsScmFlowDefinition)
        definition_xml = f"""
    <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
      <scm class="hudson.plugins.git.GitSCM" plugin="git">
        <configVersion>2</configVersion>
        <userRemoteConfigs>
          <hudson.plugins.git.UserRemoteConfig>
            <url>{git_url}</url>
          </hudson.plugins.git.UserRemoteConfig>
        </userRemoteConfigs>
        <branches>
          <hudson.plugins.git.BranchSpec>
            <name>*/{git_branch}</name>
          </hudson.plugins.git.BranchSpec>
        </branches>
        <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      </scm>
      <scriptPath>{jenkinsfile_path}</scriptPath>
      <lightweight>true</lightweight>
    </definition>"""
    else:
        # Bare minimum (no SCM, no script)
        definition_xml = ""

    return f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>{_escape_xml(description)}</description>
  <keepDependencies>false</keepDependencies>
  <properties/>
{definition_xml}
  <triggers/>
  <disabled>false</disabled>
</flow-definition>"""


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
