// SSE Event Types
export interface SSEStepEvent { type: 'step'; data: StepStatus; }
export interface SSEResultEvent { type: 'result'; data: AnalyzeResponse; }
export interface SSEErrorEvent { type: 'error'; data: { message: string }; }
export type SSEEvent = SSEStepEvent | SSEResultEvent | SSEErrorEvent;

// API Response Types
export interface StepStatus {
  step: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  message?: string;
}

export interface AttackScenario {
  id: string;
  mitre_technique: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
  container: string;
  objective: string;
  executed_command: string;
  command_output: string;
  security_finding: string;
}

export interface PolicyViolation {
  rule: string;
  severity: string;
  message: string;
  recommendation: string;
}

export interface VulnerabilityItem {
  id: string;
  severity: string;
  category: string;
  affected_resource: string;
  title: string;
  description: string;
  remediation: string;
}

export interface ResourceReproduction {
  resource: string;
  docker_image: string;
  status: 'pass' | 'partial';
  note: string;
}

export interface SecurityResult {
  final_report: string;
  improved_bicep_code: string;
  vulnerability_summary: number;
  severity_counts: Record<string, number>;
  verification_checklist: string[];
  attack_scenarios: AttackScenario[];
  reproduction_fidelity: number | null;
  reproduction_details?: Record<string, string>;
  resource_reproduction?: ResourceReproduction[];
  vulnerabilities?: VulnerabilityItem[];
  simulation_conclusion?: string;
}

export interface PolicySummary {
  violations: number;
  recommendations: number;
  violation_details?: PolicyViolation[];
  recommendation_details?: PolicyViolation[];
}

export interface AnalyzeResponse {
  status: 'success' | 'error';
  task_id: string;
  steps: StepStatus[];
  policy?: PolicySummary;
  security?: SecurityResult;
  error?: string;
}

