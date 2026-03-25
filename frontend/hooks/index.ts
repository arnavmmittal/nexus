// Skills hooks
export {
  useSkills,
  useSkill,
  useSkillsWidget,
  useCreateSkill,
  useLogSkillXP,
  useDeleteSkill,
  skillKeys,
} from './useSkills';

// Goals hooks
export {
  useGoals,
  useGoal,
  useGoalsWidget,
  useCreateGoal,
  useUpdateGoal,
  useLogGoalProgress,
  useDeleteGoal,
  goalKeys,
} from './useGoals';

// Chat hooks
export {
  useChat,
  useStreamingChat,
  useChatMutation,
} from './useChat';

// Widget hooks
export {
  useTodaysFocus,
  useMoneyWidget,
  useHealthWidget,
  widgetKeys,
} from './useWidgets';

// Integration hooks
export {
  useIntegrationsStatus,
  useGoogleAuth,
  useGitHub,
  usePlaidIntegration,
  integrationKeys,
} from './useIntegrations';

// PWA hooks
export {
  usePWA,
  useNotifications,
  type PWAStatus,
  type UsePWAReturn,
  type NotificationPermission,
  type UseNotificationsReturn,
} from './pwa';
