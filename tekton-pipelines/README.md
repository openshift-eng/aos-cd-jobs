# Tekton Demo: Put the link to GitHub Pull Request to JIRA

## Prerequisites
- A Kubernetes cluster version 1.15+ or OpenShift cluster 3.11+.
  Use [Minikube][] to runs a single-node Kubernetes cluster in a virtual machine on your personal computer.

- Tekton Pipelines
    ``` sh
    # Kubernetes
    kubectl apply -f https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml
    # OpenShift
    oc apply -f https://storage.googleapis.com/tekton-releases/pipeline/latest/release.notags.yaml
    ```
    ``` sh
    # check for installation
    kubectl get pods --namespace tekton-pipelines
    kubectl get svc -n tekton-pipelines tekton-dashboard
    ```
- Tekton Triggers
    ``` sh
    kubectl apply -f https://storage.googleapis.com/tekton-releases/triggers/latest/release.yaml
    ```
    ``` sh
    # check for installation
    kubectl get pods --namespace tekton-pipelines
    ```
- (Optional) Tekton Dashboard
    ``` sh
    # Kubernetes
    kubectl apply -f https://github.com/tektoncd/dashboard/releases/latest/download/tekton-dashboard-release.yaml
    # OpenShift
    oc apply -f https://github.com/tektoncd/dashboard/releases/latest/download/openshift-tekton-dashboard-release.yaml
    ```
    ``` sh
    # check for installation
    kubectl get pods --namespace tekton-pipelines
    kubectl get svc -n tekton-pipelines tekton-dashboard
    ```
- (Optional) Tekton CLI
    ```sh
    # Linux
    curl -LO https://github.com/tektoncd/cli/releases/download/v0.10.0/tkn_0.10.0_Linux_x86_64.tar.gz
    tar -xvzf tkn_0.10.0_Linux_x86_64.tar.gz -C /usr/local/bin/ tkn
    # macOS
    brew tap tektoncd/tools
    brew install tektoncd/tools/tektoncd-cli
    ```
    ``` sh
    # check for installation
    tkn version
    ```

# Create and Run a Task
- Edit `secrets/jira.yaml` for your issues.redhat.com username and password.
  Then create a secret:
  ``` sh
  kubectl apply -f secrets/jira.yaml
  ```
- Create a task:
  ```sh
  kubectl apply -f tasks/jira-set-link-to-pr.yaml
  ```
  List all created tasks:
  ```sh
  kubectl get tasks
  # or
  tkn task list
  ```
- Run a standalone task:
  Manually create a TaskRun named `jira-set-link-to-pr-run-1`:
  ```yaml
  apiVersion: tekton.dev/v1beta1
  kind: TaskRun
  metadata:
    name: jira-set-link-to-pr-run-1
  spec:
    params:
    - name: REPO_FULL_NAME
      value: vfreex/elliott
    - name: PR_NUMBER
      value: "1"
    serviceAccountName: ""
    taskRef:
      name: jira-set-link-to-pr
  ```
  Or use the `tkn` command:
  ```sh
  # interactively
  tkn task start jira-set-link-to-pr
  # or non-interactively
  tkn task start jira-set-link-to-pr -p REPO_FULL_NAME=vfreex/elliott -p PR_NUMBER=1
  ```
- See logs:
  ``` sh
  tkn taskrun logs --last -f
  ```
- List all taskruns:
  ```sh
  kubectl get taskruns
  # or
  tkn taskrun list
  ```

## Create and Run a Pipeline
- Create a pipeline:
  ```sh
  kubectl apply -f pipelines/link-pull-request-to-jira.yaml
  ```
- List all pipelines:
  ```
  kubectl get pipelines
  # or
  tkn pipeline list
  ```
- Run a pipeline:
  Manually create a PipelineRun named `link-pull-request-to-jira-run-1`:
  ```yaml
  apiVersion: tekton.dev/v1beta1
  kind: PipelineRun
  metadata:
    name: link-pull-request-to-jira-run-1
  spec:
    params:
    - name: PR_NUMBER
      value: "1"
    - name: REPO_FULL_NAME
      value: vfreex/elliott
    pipelineRef:
      name: link-pull-request-to-jira
  ```
  Or use the `tkn` command:
  ```sh
  # interactively
  tkn pipeline start link-pull-request-to-jira
  # or non-interactively
  tkn pipeline start link-pull-request-to-jira -p REPO_FULL_NAME=vfreex/elliott -p PR_NUMBER=1
  ```
- See logs:
  ``` sh
  tkn pipelinerun logs --last -f
  ```
- List all pipelines:
  ```sh
  kubectl get pipelineruns
  # or
  tkn pipelinerun list
  ```

## Automatically Trigger a PipelineRun using GitHub Webhooks
- Add a TriggerBinding to convert GitHub webhook payload to parameters and a TriggerTemplate to template PipelineRun resource:
  ```sh
  kubectl apply -f ./triggers/link-pull-request-to-jira.yaml
  ```
- Add an EventListener.

  Edit `secrets/github-webhook.yaml` for your webhook secret then add it to Kubernetes:
  ```sh
  kubectl apply -f secrets/github-webhook.yaml
  ```
  Create the EventListener:
  ```sh
  kubectl apply -f infra/rbac.yaml
  kubectl apply -f infra/github-event-listener.yaml
  ```
- (On a public cloud) Expose the EventListener service via Ingress or Route.
  ``` sh
  # OpenShift
  oc expose service/el-github-event-listener
  ```
- Add a webhook to your GitHub repo:
  ```
  # Settings -> Webhook -> Add webhook
  Payload URL: your exposed event listener URL
  Content type: application/json
  Secret: your secret in secrets/github-webhook.yaml
  Which events would you like to trigger this webhook? "Let me select individual events." Check "Pull requests".
  Active: check
  ```
- Test your trigger
  Forward your local 8080 port to the event listener pod:
  ```sh
  kubectl get po -l eventlistener=github-event-listener
  kubectl port-forward <pod-name> 8080
  ```
  Send a webhook payload. For example:
  ```sh
  curl -v \
    -H 'X-GitHub-Event: pull_request' \
    -H 'X-Hub-Signature: sha1=13eaa0168f8d8efcdf5189ea75b782cf89809de6' \
    -H 'Content-Type: application/json' \
    -d '{"action": "opened", "head_commit":{"id":"master"},"repository":{"url": "https://github.com/tektoncd/triggers"}}' \
    http://localhost:8080
  ```
  See [Webhook event payloads][] for the format.
## (Optional) Proxy GitHub webhook behind a secure firewall with smee.io
- Create a new channel at https://smee.io/.
- Run `smee` CLI behind your firewall.
  ```sh
  # forward https://smee.io/<channel> to https://127.0.0.1:8080
  smee -u https://smee.io/<channel> -t https://127.0.0.1:8080
  ```
- Go to your GitHub repo webhook settings, use `https://smee.io/<channel>` as the Payload URL.

## Cleanup
```sh
kubectl delete pipelineruns --all
kubectl delete pipelines --all
kubectl delete taskruns --all
kubectl delete tasks --all
kubectl delete eventlisteners --all
kubectl delete triggerbindings --all
kubectl delete triggertemplates --all
```

[Minikube]: https://kubernetes.io/docs/tasks/tools/install-minikube/
[Webhook event payloads]: https://developer.github.com/webhooks/event-payloads/#pull_request
